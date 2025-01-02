from log_processor.log import Log

if __name__ == "__main__":
    log = Log.load_from_files("output/test.chat", "output/log")

    summary = log.get_summary()
    with open("output/summary.md", "w") as f:
        f.write(summary)

