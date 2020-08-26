import DungeonRandomizer



while True:
    try:
        DungeonRandomizer.start()
    except KeyboardInterrupt:
        break
    except Exception as e: 
        print(e)
        continue
    break

