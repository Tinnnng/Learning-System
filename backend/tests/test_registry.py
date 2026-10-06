from app.modules.registry import ENABLED_MODULES, load_modules


def test_every_enabled_module_is_mounted_under_its_own_prefix(client):
    mounted_paths = set(client.app.openapi()["paths"])
    for module in load_modules():
        assert any(path.startswith(module.prefix + "/") for path in mounted_paths), module.name


def test_module_names_are_unique():
    assert len(ENABLED_MODULES) == len(set(ENABLED_MODULES))
