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
from analyzer_utils import load_config


# Regex para detectar versiones hardcodeadas del tipo "group:artifact:1.2.3"
# No detecta: project(':module'), libs.xxx (version catalog)
_HARDCODED_VERSION_RE = re.compile(
    r'["\'][\w][\w.\-]*:[\w][\w.\-]*:\d[\w.\-]*["\']'
)


class GradleSanityAnalyzer:
    def __init__(self, base_path, config_path=None, verbose=True):
        self.base_path = Path(base_path)
        self.config    = load_config(config_path)
        self.weights   = self.config.get("sanity_weights", {})
        self._vprint   = print if verbose else (lambda *a, **k: None)

        self._dep = GradleDependencyAnalyzer(base_path, config_path, verbose=verbose)

        self.ca          = {}
        self.ce          = {}
        self.instability = {}

        self.cycles          = []
        self.sdp_violations  = []
        self.api_issues      = []
        self.fan_out_issues  = []
        self.version_issues  = []
        self.orphan_modules  = []

    def analyze(self):
        self._dep.scan_modules()
        self._dep.analyze_gradle_dependencies()

        self._compute_coupling()
        self._detect_sdp_violations()
        self._check_api_hygiene()
        self._check_fan_out()
        self._check_hardcoded_versions()
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

    def _check_hardcoded_versions(self):
        """
        Versiones hardcodeadas dificultan el mantenimiento en proyectos multi-módulo.
        Lo recomendado es usar Version Catalog (libs.versions.toml).
        Detecta cadenas como: "com.google.dagger:hilt-android:2.48"
        No detecta: project(':module'), libs.xxx
        """
        for module in self._dep.modules:
            module_path = self.base_path / module.replace(':', '/')
            gradle_file = module_path / "build.gradle.kts"
            if not gradle_file.exists():
                gradle_file = module_path / "build.gradle"

            if gradle_file.exists():
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

    # ── Score ─────────────────────────────────────────────────────────────────

    def compute_score(self):
        """
        Calcula el score de sanidad (0–100).
        Los pesos NO son un estándar externo — son defaults razonables
        configurables en analyzer_config.json bajo 'sanity_weights'.
        """
        w     = self.weights
        score = 100

        score -= len(self.cycles)         * w.get("cycle",             20)
        score -= len(self.sdp_violations) * w.get("sdp_violation",     10)
        score -= len(self.api_issues)     * w.get("unnecessary_api",    5)
        score -= len(self.fan_out_issues) * w.get("high_fan_out_penalty", 3)

        version_count = sum(len(versions) for _, versions in self.version_issues)
        score -= version_count * w.get("hardcoded_version", 2)

        return max(0, score)

    # ── Reporte ───────────────────────────────────────────────────────────────

    def generate_report(self):
        score   = self.compute_score()
        w       = self.weights
        modules = self._dep.modules
        SEP     = "=" * 70
        sep     = "─" * 70

        lines = [
            SEP,
            "REPORTE DE SANIDAD DE DEPENDENCIAS GRADLE",
            SEP,
            f"\nRuta analizada : {self.base_path}",
            f"Total módulos  : {len(modules)}",
            "",
        ]

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

        # ── Violaciones ───────────────────────────────────────────────────────
        lines += [
            SEP,
            "VIOLACIONES DETECTADAS",
            SEP,
            "",
        ]

        # — Ciclos
        penalty = w.get("cycle", 20)
        lines.append(f"🔴 CICLOS ({len(self.cycles)})  —  -{penalty} pts c/u")
        lines.append(
            "   Un ciclo ocurre cuando A depende de B y B depende de A (directa o indirectamente).\n"
            "   Los ciclos hacen imposible compilar los módulos por separado y rompen\n"
            "   la modularización. Son el problema más grave en arquitectura de módulos."
        )
        if self.cycles:
            for cycle in self.cycles:
                lines.append(f"   ⚠️  {' → '.join(cycle)}")
        else:
            lines.append("   Sin ciclos detectados ✅")
        lines.append("")

        # — SDP
        penalty   = w.get("sdp_violation", 10)
        threshold = w.get("sdp_threshold", 0.3)
        lines.append(f"🟠 VIOLACIONES SDP ({len(self.sdp_violations)})  —  -{penalty} pts c/u")
        lines.append(
            "   SDP = Stable Dependencies Principle (Principio de Dependencias Estables).\n"
            "   Regla: las dependencias deben apuntar hacia módulos más estables (I más bajo).\n"
           f"   Se detecta cuando I(destino) - I(origen) > {threshold} (umbral configurable).\n"
            "   Ejemplo correcto  : app (I=1.0) → common (I=0.0)  ✅\n"
            "   Ejemplo violación : common (I=0.0) → home (I=0.8)  ⚠️  — common puede\n"
            "                       verse afectado por cada cambio en home."
        )
        if self.sdp_violations:
            for (frm, to, i_frm, i_to) in self.sdp_violations:
                lines.append(f"   ⚠️  {frm} (I={i_frm:.2f}) → {to} (I={i_to:.2f})")
                lines.append(f"       └─ {frm} es más estable que {to}, pero depende de él.")
        else:
            lines.append("   Sin violaciones SDP ✅")
        lines.append("")

        # — Api innecesario
        penalty = w.get("unnecessary_api", 5)
        lines.append(f"🟡 API INNECESARIO ({len(self.api_issues)})  —  -{penalty} pts c/u")
        lines.append(
            "   El scope `api` expone dependencias a TODOS los módulos que dependen de este.\n"
            "   Si Ca = 0 (nadie depende de este módulo), ese alcance es completamente\n"
            "   innecesario y contamina el grafo de dependencias sin beneficio.\n"
            "   Solución: reemplazar `api` por `implementation`."
        )
        if self.api_issues:
            for (module, api_deps) in self.api_issues:
                lines.append(f"   ⚠️  {module}  (Ca=0, usa api para: {', '.join(sorted(api_deps))})")
        else:
            lines.append("   Sin problemas de api detectados ✅")
        lines.append("")

        # — Fan-out
        threshold = w.get("high_fan_out_threshold", 5)
        penalty   = w.get("high_fan_out_penalty", 3)
        lines.append(f"🟡 FAN-OUT EXCESIVO ({len(self.fan_out_issues)})  —  -{penalty} pts c/u")
        lines.append(
            f"   Un módulo con Ce > {threshold} depende de demasiados otros (umbral configurable).\n"
            "   Eso lo hace frágil: cualquier cambio en cualquiera de esos módulos puede\n"
            "   romperlo. Considerar agrupar dependencias o dividir el módulo."
        )
        if self.fan_out_issues:
            for (module, ce) in self.fan_out_issues:
                lines.append(f"   ⚠️  {module}  Ce={ce} (supera el umbral de {threshold})")
        else:
            lines.append("   Sin fan-out excesivo ✅")
        lines.append("")

        # — Versiones hardcodeadas
        penalty = w.get("hardcoded_version", 2)
        total_v = sum(len(v) for _, v in self.version_issues)
        lines.append(f"🔵 VERSIONES HARDCODEADAS ({total_v})  —  -{penalty} pts c/u")
        lines.append(
            "   Versiones escritas directamente en build.gradle (ej: 'com.lib:x:1.2.3')\n"
            "   en lugar de usar Version Catalog (libs.versions.toml).\n"
            "   En proyectos multi-módulo esto dificulta actualizar versiones de forma\n"
            "   consistente y puede generar conflictos entre módulos.\n"
            "   Solución: mover las versiones a libs.versions.toml."
        )
        if self.version_issues:
            for (module, versions) in self.version_issues:
                lines.append(f"   Módulo: {module}")
                for v in versions:
                    lines.append(f"     └─ {v}")
        else:
            lines.append("   Sin versiones hardcodeadas ✅")
        lines.append("")

        lines.append(f"ℹ️  MÓDULOS HUÉRFANOS ({len(self.orphan_modules)})  —  sin penalización")
        lines.append(
            "   Módulos sin dependencias entrantes (Ca=0) ni salientes (Ce=0).\n"
            "   Pueden ser features en desarrollo o candidatos a eliminar.\n"
            "   No se penalizan en el score — requieren revisión manual."
        )
        if self.orphan_modules:
            for module in sorted(self.orphan_modules):
                lines.append(f"   ℹ️  {module}")
        else:
            lines.append("   Sin módulos huérfanos ✅")
        lines.append("")

        # ── Score ─────────────────────────────────────────────────────────────
        n_cycles   = len(self.cycles)
        n_sdp      = len(self.sdp_violations)
        n_api      = len(self.api_issues)
        n_fanout   = len(self.fan_out_issues)
        n_versions = sum(len(v) for _, v in self.version_issues)

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
        return {
            "path":    str(self.base_path),
            "score":   self.compute_score(),
            "modules": {
                m: {
                    "ca": self.ca.get(m, 0),
                    "ce": self.ce.get(m, 0),
                    "I":  round(self.instability.get(m, 0.0), 2),
                }
                for m in self._dep.modules
            },
            "cycles": [c for c in self.cycles],
            "sdp_violations": [
                {"from": frm, "to": to, "I_from": round(i_frm, 2), "I_to": round(i_to, 2)}
                for frm, to, i_frm, i_to in self.sdp_violations
            ],
            "api_issues": [
                {"module": m, "api_deps": list(deps)}
                for m, deps in self.api_issues
            ],
            "fan_out_issues": [
                {"module": m, "ce": ce}
                for m, ce in self.fan_out_issues
            ],
            "version_issues": [
                {"module": m, "versions": versions}
                for m, versions in self.version_issues
            ],
            "orphan_modules": self.orphan_modules,
        }


def main():
    import sys

    parser = argparse.ArgumentParser(
        description='Mide la sanidad arquitectónica de las dependencias Gradle de un módulo Android'
    )
    parser.add_argument('path')
    parser.add_argument('--output-dir', default='sanity', dest='output_dir', metavar='DIR')
    parser.add_argument('--config',     default=None, metavar='PATH')
    parser.add_argument('--quiet',      action='store_true')
    parser.add_argument('--json',       action='store_true')
    parser.add_argument('--fail-on-cycle',        action='store_true', dest='fail_on_cycle')
    parser.add_argument('--fail-on-score-below',  type=int, default=None, dest='fail_below', metavar='N')

    args = parser.parse_args()

    if not args.quiet:
        print("🏥 Analizador de Sanidad de Dependencias Gradle")
        print("=" * 70)

    analyzer = GradleSanityAnalyzer(
        base_path=args.path,
        config_path=args.config,
        verbose=not args.quiet,
    )
    analyzer.analyze()
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
