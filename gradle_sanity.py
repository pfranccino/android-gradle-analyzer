#!/usr/bin/env python3
"""
Analizador de sanidad de dependencias Gradle
Mide la salud arquitectónica de un proyecto Android multi-módulo.

Métricas calculadas:
  Ca  — Afferent Coupling  : cuántos módulos dependen de este
  Ce  — Efferent Coupling  : cuántos módulos usa este
  I   — Instability        : Ce / (Ce + Ca), rango 0.0–1.0

Problemas detectados:
  - Ciclos de dependencia
  - Violaciones SDP (módulo estable que depende de uno inestable)
  - Scope `api` innecesario (Ca = 0, nadie consume las deps transitivas)
  - Fan-out excesivo (Ce > umbral configurable)
  - Versiones de dependencias hardcodeadas (en lugar de Version Catalog)
"""

import re
import argparse
from pathlib import Path
from collections import defaultdict

from gradle_analyzer import GradleDependencyAnalyzer
from dependency_engine import EngineError
from analyzer_utils import load_config, load_project_config, _strip_comments


# Regex para detectar versiones hardcodeadas del tipo "group:artifact:1.2.3"
# No detecta: project(':module'), libs.xxx (version catalog)
_HARDCODED_VERSION_RE = re.compile(
    r'["\'][\w][\w.\-]*:[\w][\w.\-]*:\d[\w.\-]*["\']'
)


class GradleSanityAnalyzer:
    def __init__(self, base_path, config_path=None, verbose=True, engine="static",
                 focus=None):
        self.base_path = Path(base_path)
        self.config    = load_config(config_path)
        self.weights   = self.config.get("sanity_weights", {})
        self._vprint   = print if verbose else (lambda *a, **k: None)

        # El grafo (y por tanto Ca/Ce/I) se calcula SIEMPRE sobre el proyecto
        # completo. `focus` solo centra el reporte y el score: así un módulo
        # conserva su Ca real (sus llamadores cuentan aunque estén fuera del foco).
        self._dep = GradleDependencyAnalyzer(base_path, config_path, verbose=verbose,
                                             engine=engine, focus=focus)
        self.focus_modules = []
        self._focus_set    = set()

        self.ca          = {}
        self.ce          = {}
        self.instability = {}

        self.cycles          = []
        self.sdp_violations  = []
        self.api_issues      = []
        self.fan_out_issues  = []
        self.version_issues  = []
        self.orphan_modules  = []
        self.coupling_issues = []   # [(module, kind, I, ca, max_ca)] · kind: "app"|"feature"

    def analyze(self):
        self._dep.scan_modules()
        self._dep.analyze_gradle_dependencies()

        # Foco = los módulos enfocados del grafo (subárbol o módulo elegido).
        # Si abarca todo el proyecto, el reporte es el de siempre.
        self.focus_modules = list(self._dep.focus_modules) or list(self._dep.modules)
        self._focus_set    = set(self.focus_modules)

        self._compute_coupling()
        self._detect_sdp_violations()
        self._check_api_hygiene()
        self._check_fan_out()
        self._check_hardcoded_versions()
        self._check_leaf_coupling()
        return self

    def _compute_coupling(self):
        modules      = self._dep.modules
        dependencies = self._dep.dependencies

        # Ce = módulos únicos de los que dependo (cualquier scope)
        for module in modules:
            deps_flat = set()
            for scope_deps in dependencies.get(module, {}).values():
                deps_flat.update(scope_deps)
            self.ce[module] = len(deps_flat)
            self.ca[module] = 0

        # Ca = cuántos módulos me apuntan a mí
        for module in modules:
            for scope_deps in dependencies.get(module, {}).values():
                for dep in scope_deps:
                    if dep in self.ca:
                        self.ca[dep] += 1

        # I = Ce / (Ce + Ca)
        for module in modules:
            total = self.ca[module] + self.ce[module]
            self.instability[module] = self.ce[module] / total if total > 0 else 0.0

        self.cycles = self._dep.detect_dependency_cycles()

        self.orphan_modules = [
            m for m in self._dep.modules
            if self.ca.get(m, 0) == 0 and self.ce.get(m, 0) == 0
        ]

    def _detect_sdp_violations(self):
        """
        SDP — Stable Dependencies Principle:
        Las dependencias deben apuntar hacia módulos más estables (I más bajo).
        Violación: módulo A (I bajo = estable) depende de módulo B (I alto = inestable).
        """
        threshold    = self.weights.get("sdp_threshold", 0.3)
        dependencies = self._dep.dependencies

        for module in self._dep.modules:
            i_from   = self.instability.get(module, 0.0)
            all_deps = set()
            for scope_deps in dependencies.get(module, {}).values():
                all_deps.update(scope_deps)

            for dep in all_deps:
                i_to = self.instability.get(dep, 0.0)
                # Violación: el destino es significativamente más inestable que el origen
                if i_to - i_from > threshold:
                    self.sdp_violations.append((module, dep, i_from, i_to))

    def _check_api_hygiene(self):
        """
        El scope `api` hace que las dependencias sean visibles para TODOS
        los módulos que dependen de este. Si Ca = 0 (nadie depende de este módulo),
        ese alcance es completamente innecesario — usar `implementation` es suficiente.
        """
        for module in self._dep.modules:
            if self.ca.get(module, 0) == 0:
                api_deps = self._dep.dependencies.get(module, {}).get('api', set())
                if api_deps:
                    self.api_issues.append((module, api_deps))

    def _check_fan_out(self):
        """
        Fan-out excesivo: un módulo que depende de demasiados otros es frágil.
        Cualquier cambio en cualquiera de esos módulos puede romperte.
        """
        threshold = self.weights.get("high_fan_out_threshold", 5)
        for module in self._dep.modules:
            ce = self.ce.get(module, 0)
            if ce > threshold:
                self.fan_out_issues.append((module, ce))

    def _gradle_file_for(self, module: str) -> Path | None:
        """Devuelve el build.gradle(.kts) de un módulo, o None si no existe."""
        module_path = self.base_path / module.replace(':', '/')
        for name in ("build.gradle.kts", "build.gradle"):
            candidate = module_path / name
            if candidate.exists():
                return candidate
        return None

    def _check_hardcoded_versions(self):
        """
        Versiones hardcodeadas dificultan el mantenimiento en proyectos multi-módulo.
        Lo recomendado es usar Version Catalog (libs.versions.toml).
        Detecta cadenas como: "com.google.dagger:hilt-android:2.48"
        No detecta: project(':module'), libs.xxx
        """
        for module in self._dep.modules:
            gradle_file = self._gradle_file_for(module)
            if gradle_file is not None:
                try:
                    content = gradle_file.read_text(encoding='utf-8')
                    active = "\n".join(
                        l for l in content.splitlines()
                        if not l.strip().startswith(('//', '*', '/*'))
                    )
                    matches = _HARDCODED_VERSION_RE.findall(active)
                    if matches:
                        self.version_issues.append((module, matches))
                except Exception as e:
                    print(f"  ⚠️  Error leyendo {gradle_file.name}: {e}")

    def _is_app(self, module: str) -> bool:
        """
        Determina si un módulo es el punto de entrada (app).
        Precedencia: override explícito en `coupling_overrides`, luego la única señal
        de plugin confiable: `com.android.application` en el build file.
        No resuelve `alias(libs.plugins...)` (requiere el version catalog).
        """
        overrides = self.config.get("coupling_overrides", {})
        forced = overrides.get(module) or overrides.get(module.split(":")[-1])
        if forced == "app":
            return True
        if forced in ("leaf", "ignore"):
            return False

        gradle_file = self._gradle_file_for(module)
        if gradle_file is None:
            return False
        try:
            content = _strip_comments(gradle_file.read_text(encoding='utf-8'))
        except Exception:
            return False
        return "com.android.application" in content

    def _check_leaf_coupling(self):
        """
        Detecta "lógica compartida mal ubicada": un módulo de alto nivel (feature o app:
        I alto, en la punta del grafo de dependencias) del que sin embargo otros dependen.
        Suele indicar código común atrapado arriba en vez de bajar a core/shared.

        La I baja de core/common los excluye automáticamente — un módulo base con Ca alto
        es esperado, no un problema. No depende de nombres ni de plugins (salvo el refinamiento
        opcional de `com.android.application` para distinguir el punto de entrada).
        """
        limits   = self.config.get("coupling_limits", {})
        leaf_i   = limits.get("leaf_instability", 0.70)
        leaf_ca  = limits.get("leaf_max_ca", 1)
        app_ca   = limits.get("app_max_ca", 0)
        overrides = self.config.get("coupling_overrides", {})

        for module in self._dep.modules:
            forced = overrides.get(module) or overrides.get(module.split(":")[-1])
            if forced == "ignore":
                continue
            i = self.instability.get(module, 0.0)
            if i < leaf_i:
                continue   # core/shared: Ca alto es legítimo, no es una hoja
            ca     = self.ca.get(module, 0)
            is_app = self._is_app(module)
            max_ca = app_ca if is_app else leaf_ca
            if ca > max_ca:
                kind = "app" if is_app else "feature"
                self.coupling_issues.append((module, kind, round(i, 2), ca, max_ca))

    # ── Foco ────────────────────────────────────────────────────────────────────

    def _focused_issues(self):
        """Filtra las violaciones (detectadas sobre el grafo completo) a las que
        tienen un módulo del foco como SUJETO. Con foco = proyecto, no filtra nada."""
        fs = self._focus_set
        return {
            "cycles":   [c for c in self.cycles          if fs.intersection(c)],
            "sdp":      [v for v in self.sdp_violations   if v[0] in fs],
            "api":      [x for x in self.api_issues       if x[0] in fs],
            "fan_out":  [x for x in self.fan_out_issues   if x[0] in fs],
            "versions": [x for x in self.version_issues   if x[0] in fs],
            "orphans":  [m for m in self.orphan_modules   if m in fs],
            "coupling": [x for x in self.coupling_issues  if x[0] in fs],
        }

    @property
    def is_focused(self):
        """True si el foco es un subconjunto estricto del proyecto."""
        return bool(self.focus_modules) and self._focus_set != set(self._dep.modules)

    def _neighbors(self, module):
        """(llamadores, llamados) de `module` en el grafo COMPLETO.
        - llamadores (Ca): quién depende de este módulo.
        - llamados (Ce):  de qué módulos depende este."""
        deps = self._dep.dependencies
        callees = set()
        for scope_deps in deps.get(module, {}).values():
            callees |= scope_deps
        callers = set()
        for other in self._dep.modules:
            for scope_deps in deps.get(other, {}).values():
                if module in scope_deps:
                    callers.add(other)
                    break
        return callers, callees

    # ── Score ─────────────────────────────────────────────────────────────────

    def compute_score(self):
        """
        Calcula el score de sanidad (0–100) sobre las violaciones del foco
        (todas, si el foco es el proyecto completo).
        Los pesos NO son un estándar externo — son defaults razonables
        configurables en analyzer_config.json bajo 'sanity_weights'.
        """
        w     = self.weights
        f     = self._focused_issues()
        score = 100

        score -= len(f["cycles"])  * w.get("cycle",              20)
        score -= len(f["sdp"])     * w.get("sdp_violation",      10)
        score -= len(f["api"])     * w.get("unnecessary_api",     5)
        score -= len(f["fan_out"]) * w.get("high_fan_out_penalty", 3)

        version_count = sum(len(versions) for _, versions in f["versions"])
        score -= version_count * w.get("hardcoded_version", 2)

        limits = self.config.get("coupling_limits", {})
        for _module, kind, _i, _ca, _max_ca in f["coupling"]:
            score -= limits.get("app_penalty", 0) if kind == "app" else limits.get("leaf_penalty", 0)

        return max(0, score)

    # ── Reporte ───────────────────────────────────────────────────────────────

    def generate_report(self):
        score   = self.compute_score()
        w       = self.weights
        f       = self._focused_issues()
        modules = sorted(self.focus_modules)
        SEP     = "=" * 70
        sep     = "─" * 70

        lines = [
            SEP,
            "REPORTE DE SANIDAD DE DEPENDENCIAS GRADLE",
            SEP,
            f"\nRuta analizada : {self.base_path}",
        ]
        if self.is_focused:
            lines += [
                f"Foco           : {', '.join(modules)}",
                f"Módulos foco   : {len(modules)}  (Ca/Ce/I medidos en el contexto"
                f" del proyecto completo: {len(self._dep.modules)} módulos)",
                "",
            ]
        else:
            lines += [f"Total módulos  : {len(modules)}", ""]

        # ── Glosario ─────────────────────────────────────────────────────────
        lines += [
            SEP,
            "GLOSARIO — ¿QUÉ MIDE CADA COLUMNA?",
            SEP,
            "",
            "  Ca  (Afferent Coupling — acoplamiento aferente)",
            "      Cuántos módulos dependen de ESTE módulo (flechas que llegan).",
            "      Ca alto → módulo crítico. Cambiar su API afecta a muchos.",
            "      Esperado alto en: common, core, shared.",
            "",
            "  Ce  (Efferent Coupling — acoplamiento eferente)",
            "      Cuántos módulos usa ESTE módulo (flechas que salen).",
            "      Ce alto → módulo frágil. Cambios externos pueden romperlo.",
            "      Esperado alto en: app, features de alto nivel.",
            "",
            "  I   (Instability — inestabilidad = Ce / (Ce + Ca))",
            "      Qué tan fácil es cambiar este módulo sin romper a otros.",
            "      I = 0.00 → muy ESTABLE   (ideal para módulos base: common, core)",
            "      I = 1.00 → muy INESTABLE (ideal para módulos hoja: app, features)",
            "",
            "      ⚠️  El valor de I no es bueno ni malo por sí solo.",
            "          Lo que importa es la DIRECCIÓN de las flechas:",
            "          las dependencias deben apuntar de I alto → I bajo.",
            "          Si un módulo estable (I bajo) depende de uno inestable (I alto)",
            "          → eso es una violación arquitectónica (SDP).",
            "",
        ]

        # ── Tabla de métricas ─────────────────────────────────────────────────
        lines += [
            SEP,
            "MÉTRICAS POR MÓDULO",
            SEP,
            "",
            f"  {'Módulo':<30} {'Ca':>4}  {'Ce':>4}  {'I':>6}  Estado",
            f"  {sep[:30]}  {sep[:4]}  {sep[:4]}  {sep[:6]}  {sep[:30]}",
        ]

        for module in sorted(modules):
            ca = self.ca.get(module, 0)
            ce = self.ce.get(module, 0)
            i  = self.instability.get(module, 0.0)

            if i <= 0.25:
                estado = "🟢 Estable"
            elif i <= 0.60:
                estado = "🟡 Moderadamente estable"
            elif i <= 0.85:
                estado = "🟠 Moderadamente inestable"
            else:
                estado = "🔴 Inestable (módulo hoja)"

            lines.append(f"  {module:<30} {ca:>4}  {ce:>4}  {i:>6.2f}  {estado}")

        lines.append("")

        # ── Vecinos del foco (ambas direcciones) ──────────────────────────────
        # Con foco mostramos, por módulo, quién lo llama (Ca) y a quién llama (Ce),
        # medido sobre el grafo completo. Sin foco se omite (sería todo el grafo).
        if self.is_focused:
            lines += [
                SEP,
                "DEPENDENCIAS DEL FOCO — AMBAS DIRECCIONES",
                SEP,
                "",
            ]
            for module in sorted(self.focus_modules):
                callers, callees = self._neighbors(module)
                ca = self.ca.get(module, 0)
                ce = self.ce.get(module, 0)
                i  = self.instability.get(module, 0.0)
                lines.append(f"  📦 {module}   (Ca={ca}  Ce={ce}  I={i:.2f})")
                lines.append(
                    f"     ← lo llaman ({len(callers)}): " +
                    (", ".join(sorted(callers)) if callers else "nadie")
                )
                lines.append(
                    f"     → depende de ({len(callees)}): " +
                    (", ".join(sorted(callees)) if callees else "nada")
                )
                lines.append("")

        # ── Violaciones ───────────────────────────────────────────────────────
        lines += [
            SEP,
            "VIOLACIONES DETECTADAS",
            SEP,
            "",
        ]

        # — Ciclos
        penalty = w.get("cycle", 20)
        lines.append(f"🔴 CICLOS ({len(f['cycles'])})  —  -{penalty} pts c/u")
        lines.append(
            "   Un ciclo ocurre cuando A depende de B y B depende de A (directa o indirectamente).\n"
            "   Los ciclos hacen imposible compilar los módulos por separado y rompen\n"
            "   la modularización. Son el problema más grave en arquitectura de módulos."
        )
        if f["cycles"]:
            for cycle in f["cycles"]:
                lines.append(f"   ⚠️  {' → '.join(cycle)}")
        else:
            lines.append("   Sin ciclos detectados ✅")
        lines.append("")

        # — SDP
        penalty   = w.get("sdp_violation", 10)
        threshold = w.get("sdp_threshold", 0.3)
        lines.append(f"🟠 VIOLACIONES SDP ({len(f['sdp'])})  —  -{penalty} pts c/u")
        lines.append(
            "   SDP = Stable Dependencies Principle (Principio de Dependencias Estables).\n"
            "   Regla: las dependencias deben apuntar hacia módulos más estables (I más bajo).\n"
           f"   Se detecta cuando I(destino) - I(origen) > {threshold} (umbral configurable).\n"
            "   Ejemplo correcto  : app (I=1.0) → common (I=0.0)  ✅\n"
            "   Ejemplo violación : common (I=0.0) → home (I=0.8)  ⚠️  — common puede\n"
            "                       verse afectado por cada cambio en home."
        )
        if f["sdp"]:
            for (frm, to, i_frm, i_to) in f["sdp"]:
                lines.append(f"   ⚠️  {frm} (I={i_frm:.2f}) → {to} (I={i_to:.2f})")
                lines.append(f"       └─ {frm} es más estable que {to}, pero depende de él.")
        else:
            lines.append("   Sin violaciones SDP ✅")
        lines.append("")

        # — Api innecesario
        penalty = w.get("unnecessary_api", 5)
        lines.append(f"🟡 API INNECESARIO ({len(f['api'])})  —  -{penalty} pts c/u")
        lines.append(
            "   El scope `api` expone dependencias a TODOS los módulos que dependen de este.\n"
            "   Si Ca = 0 (nadie depende de este módulo), ese alcance es completamente\n"
            "   innecesario y contamina el grafo de dependencias sin beneficio.\n"
            "   Solución: reemplazar `api` por `implementation`."
        )
        if f["api"]:
            for (module, api_deps) in f["api"]:
                lines.append(f"   ⚠️  {module}  (Ca=0, usa api para: {', '.join(sorted(api_deps))})")
        else:
            lines.append("   Sin problemas de api detectados ✅")
        lines.append("")

        # — Fan-out
        threshold = w.get("high_fan_out_threshold", 5)
        penalty   = w.get("high_fan_out_penalty", 3)
        lines.append(f"🟡 FAN-OUT EXCESIVO ({len(f['fan_out'])})  —  -{penalty} pts c/u")
        lines.append(
            f"   Un módulo con Ce > {threshold} depende de demasiados otros (umbral configurable).\n"
            "   Eso lo hace frágil: cualquier cambio en cualquiera de esos módulos puede\n"
            "   romperlo. Considerar agrupar dependencias o dividir el módulo."
        )
        if f["fan_out"]:
            for (module, ce) in f["fan_out"]:
                lines.append(f"   ⚠️  {module}  Ce={ce} (supera el umbral de {threshold})")
        else:
            lines.append("   Sin fan-out excesivo ✅")
        lines.append("")

        # — Versiones hardcodeadas
        penalty = w.get("hardcoded_version", 2)
        total_v = sum(len(v) for _, v in f["versions"])
        lines.append(f"🔵 VERSIONES HARDCODEADAS ({total_v})  —  -{penalty} pts c/u")
        lines.append(
            "   Versiones escritas directamente en build.gradle (ej: 'com.lib:x:1.2.3')\n"
            "   en lugar de usar Version Catalog (libs.versions.toml).\n"
            "   En proyectos multi-módulo esto dificulta actualizar versiones de forma\n"
            "   consistente y puede generar conflictos entre módulos.\n"
            "   Solución: mover las versiones a libs.versions.toml."
        )
        if f["versions"]:
            for (module, versions) in f["versions"]:
                lines.append(f"   Módulo: {module}")
                for v in versions:
                    lines.append(f"     └─ {v}")
        else:
            lines.append("   Sin versiones hardcodeadas ✅")
        lines.append("")

        lines.append(f"ℹ️  MÓDULOS HUÉRFANOS ({len(f['orphans'])})  —  sin penalización")
        lines.append(
            "   Módulos sin dependencias entrantes (Ca=0) ni salientes (Ce=0).\n"
            "   Pueden ser features en desarrollo o candidatos a eliminar.\n"
            "   No se penalizan en el score — requieren revisión manual."
        )
        if f["orphans"]:
            for module in sorted(f["orphans"]):
                lines.append(f"   ℹ️  {module}")
        else:
            lines.append("   Sin módulos huérfanos ✅")
        lines.append("")

        # — Lógica compartida mal ubicada
        cl       = self.config.get("coupling_limits", {})
        leaf_pen = cl.get("leaf_penalty", 0)
        app_pen  = cl.get("app_penalty", 0)
        if leaf_pen == 0 and app_pen == 0:
            pen_note = "informativo (sin penalización)"
        else:
            pen_note = f"feature -{leaf_pen} / app -{app_pen} pts"
        lines.append(f"🟠 LÓGICA COMPARTIDA MAL UBICADA ({len(f['coupling'])})  —  {pen_note}")
        lines.append(
            "   Un \"módulo hoja\" (término de grafos para el extremo de I alto del árbol de\n"
            "   dependencias) — es decir, un feature o el punto de entrada de la app — del que\n"
            "   sin embargo OTROS dependen. Suele indicar código común atrapado arriba en lugar\n"
            "   de bajar a core/shared. La I baja de core/common los excluye automáticamente."
        )
        if f["coupling"]:
            for (module, kind, i, ca, max_ca) in f["coupling"]:
                etiqueta = "punto de entrada" if kind == "app" else "feature"
                lines.append(f"   ⚠️  {module}  [{etiqueta}]  I={i:.2f}  Ca={ca} (límite: {max_ca})")
        else:
            lines.append("   Sin lógica compartida mal ubicada ✅")
        lines.append("")

        # ── Score ─────────────────────────────────────────────────────────────
        n_cycles   = len(f["cycles"])
        n_sdp      = len(f["sdp"])
        n_api      = len(f["api"])
        n_fanout   = len(f["fan_out"])
        n_versions = sum(len(v) for _, v in f["versions"])
        n_coupling   = len(f["coupling"])
        coupling_pts = sum(
            cl.get("app_penalty", 0) if kind == "app" else cl.get("leaf_penalty", 0)
            for _m, kind, _i, _ca, _max in f["coupling"]
        )

        lines += [
            SEP,
            "PUNTUACIÓN DE SANIDAD",
            SEP,
            "",
            "  Los pesos NO son un estándar externo. Son defaults razonables.",
            "  Puedes ajustarlos en analyzer_config.json bajo 'sanity_weights'.",
            "",
            f"  {'Puntaje base:':<45} {'100':>6}",
            f"  {'Ciclos (' + str(n_cycles) + ' × ' + str(w.get('cycle', 20)) + ' pts):':<45} {'-' + str(n_cycles * w.get('cycle', 20)):>6}",
            f"  {'Violaciones SDP (' + str(n_sdp) + ' × ' + str(w.get('sdp_violation', 10)) + ' pts):':<45} {'-' + str(n_sdp * w.get('sdp_violation', 10)):>6}",
            f"  {'Api innecesario (' + str(n_api) + ' × ' + str(w.get('unnecessary_api', 5)) + ' pts):':<45} {'-' + str(n_api * w.get('unnecessary_api', 5)):>6}",
            f"  {'Fan-out excesivo (' + str(n_fanout) + ' × ' + str(w.get('high_fan_out_penalty', 3)) + ' pts):':<45} {'-' + str(n_fanout * w.get('high_fan_out_penalty', 3)):>6}",
            f"  {'Versiones hardcodeadas (' + str(n_versions) + ' × ' + str(w.get('hardcoded_version', 2)) + ' pts):':<45} {'-' + str(n_versions * w.get('hardcoded_version', 2)):>6}",
            f"  {'Lógica compartida mal ubicada (' + str(n_coupling) + ' issue(s)):':<45} {'-' + str(coupling_pts):>6}",
            f"  {sep[:51]}",
            f"  {'PUNTUACIÓN FINAL:':<45} {score:>5} / 100",
            "",
        ]

        if score >= 90:
            nivel = "🟢 Excelente — arquitectura de dependencias muy sana"
        elif score >= 70:
            nivel = "🟡 Buena — con áreas de mejora menores"
        elif score >= 50:
            nivel = "🟠 Atención requerida en la arquitectura"
        else:
            nivel = "🔴 Refactorización urgente recomendada"

        lines += [
            "  Interpretación:",
            "    90–100 → 🟢 Excelente — arquitectura de dependencias muy sana",
            "    70–89  → 🟡 Buena — con áreas de mejora menores",
            "    50–69  → 🟠 Atención requerida en la arquitectura",
            "     0–49  → 🔴 Refactorización urgente recomendada",
            "",
            f"  Resultado: {nivel}",
            "",
        ]

        return "\n".join(lines)

    def save_report(self, output_dir="sanity"):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        report_file = output_path / "sanity-report.txt"
        report_file.write_text(self.generate_report(), encoding='utf-8')
        self._vprint(f"✓ Reporte: {report_file}")

    def to_json_dict(self) -> dict:
        f = self._focused_issues()
        return {
            "path":    str(self.base_path),
            "root":    str(self._dep.root),
            "focus":   list(self.focus_modules),
            "context_modules": len(self._dep.modules),
            "score":   self.compute_score(),
            "modules": {
                m: {
                    "ca": self.ca.get(m, 0),
                    "ce": self.ce.get(m, 0),
                    "I":  round(self.instability.get(m, 0.0), 2),
                }
                for m in sorted(self.focus_modules)
            },
            "cycles": [c for c in f["cycles"]],
            "sdp_violations": [
                {"from": frm, "to": to, "I_from": round(i_frm, 2), "I_to": round(i_to, 2)}
                for frm, to, i_frm, i_to in f["sdp"]
            ],
            "api_issues": [
                {"module": m, "api_deps": list(deps)}
                for m, deps in f["api"]
            ],
            "fan_out_issues": [
                {"module": m, "ce": ce}
                for m, ce in f["fan_out"]
            ],
            "version_issues": [
                {"module": m, "versions": versions}
                for m, versions in f["versions"]
            ],
            "orphan_modules": list(f["orphans"]),
            "coupling_issues": [
                {"module": m, "kind": kind, "I": i, "ca": ca, "max_ca": max_ca}
                for m, kind, i, ca, max_ca in f["coupling"]
            ],
        }


def main():
    import sys
    from analyzer_utils import setup_utf8
    setup_utf8()

    parser = argparse.ArgumentParser(
        description='Mide la sanidad arquitectónica de las dependencias Gradle de un módulo Android'
    )
    parser.add_argument('path')
    parser.add_argument('--focus',      default=None, metavar='MODULE[,MODULE]',
                        help='Enfoca el reporte en estos módulos (Ca/Ce/I igual se miden '
                             'en el contexto del proyecto completo)')
    parser.add_argument('--output-dir', default=None, dest='output_dir', metavar='DIR')
    parser.add_argument('--config',     default=None, metavar='PATH')
    parser.add_argument('--engine',     choices=['static', 'dynamic', 'auto'], default=None,
                        help='Motor de extracción de dependencias (default: static)')
    parser.add_argument('--quiet',      action='store_true')
    parser.add_argument('--json',       action='store_true')
    parser.add_argument('--fail-on-cycle',       action='store_const', const=True, default=None, dest='fail_on_cycle')
    parser.add_argument('--fail-on-score-below', type=int, default=None, dest='fail_below', metavar='N')

    args = parser.parse_args()

    proj_cfg = load_project_config(args.path).get('sanity', {})
    if args.output_dir is None:
        args.output_dir = proj_cfg.get('output_dir', 'sanity')
    if args.engine is None:
        args.engine = proj_cfg.get('engine', 'static')
    if args.fail_on_cycle is None:
        args.fail_on_cycle = bool(proj_cfg.get('fail_on_cycle', False))
    if args.fail_below is None:
        args.fail_below = proj_cfg.get('fail_on_score_below')

    if not args.quiet:
        print("🏥 Analizador de Sanidad de Dependencias Gradle")
        print("=" * 70)

    focus = [m.strip() for m in args.focus.split(',')] if args.focus else None
    analyzer = GradleSanityAnalyzer(
        base_path=args.path,
        config_path=args.config,
        verbose=not args.quiet,
        engine=args.engine,
        focus=focus,
    )
    try:
        analyzer.analyze()
    except EngineError as exc:
        print(f"\n❌ Motor '{args.engine}' falló: {exc}")
        sys.exit(1)
    analyzer.save_report(output_dir=args.output_dir)

    if args.json:
        import json as _json
        print(_json.dumps(analyzer.to_json_dict(), indent=2, ensure_ascii=False))
    else:
        print("\n" + analyzer.generate_report())
        if not args.quiet:
            print("=" * 70)
            print("✅ ¡Análisis completado!")
            print("=" * 70)

    exit_code = 0
    score = analyzer.compute_score()

    if args.fail_on_cycle and analyzer.cycles:
        if not args.quiet:
            print(f"\n❌ Fallo: {len(analyzer.cycles)} ciclo(s) detectado(s)")
        exit_code = 1

    if args.fail_below is not None and score < args.fail_below:
        if not args.quiet:
            print(f"\n❌ Fallo: score {score} por debajo del umbral {args.fail_below}")
        exit_code = 1

    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
