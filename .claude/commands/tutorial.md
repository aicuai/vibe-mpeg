---
name: tutorial
description: Run the vibe-mpeg interactive tutorial for environment setup and video editing walkthrough
---

Run the vibe-mpeg interactive tutorial in auto mode. Execute:

```
python3 tutorial.py --auto
```

For specific steps, use --step:
```
python3 tutorial.py --auto --step 1    # Environment check only
python3 tutorial.py --auto --step 1-3  # Steps 1 through 3
```

Steps: 1=env check, 2=install, 3=concat, 4=media dir, 5=render, 6=audio mix, 7=subtitles, 8=transitions
