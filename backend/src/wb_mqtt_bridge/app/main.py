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
    try:
        server.run()
    except KeyboardInterrupt:
        # After a graceful shutdown, uvicorn's Server.capture_signals re-raises the
        # SIGINT it captured (so an embedding program sees standard Ctrl-C semantics).
        # The asyncio runner turns that into a KeyboardInterrupt out of server.run().
        # We've already torn down cleanly by this point — swallow it for a quiet exit
        # instead of dumping a CancelledError/KeyboardInterrupt traceback. uvicorn's own
        # CLI relies on click doing this catch; our console_script must do it itself.
        pass


if __name__ == "__main__":
    main()
