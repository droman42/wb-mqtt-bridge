def main() -> None:
    import uvicorn
    uvicorn.run("wb_mqtt_bridge.app:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main() 