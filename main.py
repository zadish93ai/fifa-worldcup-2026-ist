from live_sync import sync_and_generate


def main():
    completed_scores, matches = sync_and_generate()
    print(f"Generated {len(matches)} events → world_cup_live_ist.ics")
    print(f"  Completed: {len(completed_scores)}  |  Scheduled: {len(matches) - len(completed_scores)}")


if __name__ == "__main__":
    main()
