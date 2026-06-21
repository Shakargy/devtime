from devtime.scanner.extractors.nextjs import derive_route_path, is_app_router_route


def test_basic_route_path():
    assert derive_route_path("app/api/posts/route.ts") == "/api/posts"
    assert derive_route_path("src/app/api/posts/export/route.ts") == "/api/posts/export"


def test_route_groups_stripped_no_double_slash():
    # Route groups like (payments) do not affect the URL and must not leave //.
    path = derive_route_path("app/api/(payments)/checkout/route.ts")
    assert path == "/api/checkout"
    assert "//" not in path


def test_dynamic_segments_preserved():
    assert derive_route_path("app/api/posts/[id]/approve/route.ts") == "/api/posts/[id]/approve"
    assert (
        derive_route_path("src/app/api/auth/[...nextauth]/route.ts")
        == "/api/auth/[...nextauth]"
    )


def test_is_app_router_route():
    assert is_app_router_route("app/api/posts/route.ts")
    assert is_app_router_route("src/app/api/x/route.tsx")
    assert not is_app_router_route("src/components/Button.tsx")
    assert not is_app_router_route("app/api/posts/handler.ts")
