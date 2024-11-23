from barcodeAPI.app import __version__, __title__
from barcodeAPI.app.config import settings

def test_version():
    assert __version__ == settings.API_VERSION

def test_title():
    assert __title__ == settings.PROJECT_NAME

def test_version_type():
    assert isinstance(__version__, str), "Version should be a string"

def test_title_type():
    assert isinstance(__title__, str), "Title should be a string"

def test_version_not_empty():
    assert __version__, "Version should not be empty"

def test_title_not_empty():
    assert __title__, "Title should not be empty"