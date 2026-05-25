from __future__ import annotations

def test_application_package_imports() -> None:
    import app.main

    assert app.main.app.title == "Factory Owner MVP"
