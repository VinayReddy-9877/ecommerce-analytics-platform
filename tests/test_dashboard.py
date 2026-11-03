from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_all_dashboard_pages_render():
    app = AppTest.from_file(
        str(Path(__file__).parents[1] / "dashboards/app.py"), default_timeout=30
    ).run()
    assert not app.exception
    next(r for r in app.sidebar.radio if r.label == "Workspace").set_value("Data overview").run()
    for page in ["Customers", "Operations", "Executive"]:
        next(r for r in app.sidebar.radio if r.label == "View").set_value(page).run()
        assert not app.exception
