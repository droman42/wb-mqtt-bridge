def main() -> None:
    """Bridge entry point.

    Uses uvicorn's low-level Config + Server API (not the high-level
    `uvicorn.run(...)`) so we can hand the live `Server` instance to the
    SSE manager. SSE generators poll `server.should_exit` in their loop;
    when SIGINT arrives uvicorn flips that flag BEFORE entering its
    "wait for connections to drain" phase — which is exactly the signal
    the generators need to return cleanly, so the connections actually
    drain, so the lifespan's after-`yield` shutdown phase actually runs.
    Without this hookup the 1st Ctrl-C hangs forever on the long-lived
    SSE connections (see action_plan.md §5.1 #8).
    """
    import uvicorn
    from wb_mqtt_bridge.presentation.api.sse_manager import sse_manager

    config = uvicorn.Config(
        "wb_mqtt_bridge.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
    server = uvicorn.Server(config)
    sse_manager.set_uvicorn_server(server)
    server.run()


if __name__ == "__main__":
    main()
