"""
Tests para GradleDependencyAnalyzer:
  - scan_modules: detecta módulos correctamente
  - analyze_gradle_dependencies: resuelve dependencias entre módulos
"""

from pathlib import Path

from gradle_analyzer import GradleDependencyAnalyzer

FIXTURES = Path(__file__).parent / "fixtures"


class TestGradleDependencyAnalyzer:

    def test_scan_simple_modules(self):
        """Detecta exactamente los módulos del fixture simple."""
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()

        assert "app" in analyzer.modules
        assert "core" in analyzer.modules
        assert len(analyzer.modules) == 2

    def test_analyze_simple_dependency(self):
        """app depende de core via implementation."""
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        assert "core" in analyzer.dependencies["app"].get("implementation", set())

    def test_analyze_ambiguous_no_false_positive(self):
        """
        Bug 1 (integración): payments depende de payments:common,
        quick-payments NO debe aparecer como dependencia de nadie.
        """
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "ambiguous"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        all_deps = {
            dep
            for scopes in analyzer.dependencies.values()
            for deps in scopes.values()
            for dep in deps
        }
        assert "quick-payments" not in all_deps

    def test_generate_report_returns_string(self):
        """generate_report() debe devolver un string no vacío."""
        analyzer = GradleDependencyAnalyzer(base_path=str(FIXTURES / "simple"))
        analyzer.scan_modules()
        analyzer.analyze_gradle_dependencies()

        report = analyzer.generate_report()
        assert isinstance(report, str)
        assert "app" in report
        assert "core" in report
