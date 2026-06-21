from devtime.scanner import ignore as ignore_mod


def test_hard_deny_blocks_secrets_and_vcs():
    matcher = ignore_mod.build_matcher(
        __import__("pathlib").Path("."),
        respect_gitignore=False,
        respect_devtimeignore=False,
    )
    assert matcher.match(".env")
    assert matcher.match("config/service-account-prod.json")
    assert matcher.match(".git/config")
    assert matcher.match("id_rsa")
    assert not matcher.match("src/auth/login.ts")


def test_binary_extension_detection():
    assert ignore_mod.is_binary_extension(".png")
    assert ignore_mod.is_binary_extension(".sqlite")
    assert not ignore_mod.is_binary_extension(".ts")
