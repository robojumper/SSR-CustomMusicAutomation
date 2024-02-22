# SSR Custom Music Automation

Skyward Sword Randomizer supports custom music packs. Creating one is relatively annoying,
as you need to pay attention to various details like number of streams or looping status,
manually input values into janky GUIs, and rename/copy a bunch of files.

This project is an attempt to automate these menial tasks and improve maintainability of music packs.

## Elevator Pitch

Run `convert.py new shovel_knight`, fill out the song data in `./shovel_knight/music.csv`, run `convert.py patch ./shovel_knight`,
start the game in Dolphin, and you're done.

```csv
Id,Name,Source,Loop Start,Loop End
024F95B344307BD81E219F2D53DCFC87,Guardians Awaken,,0:00:00,0:00:00
03C8C90CC621939FA47032CF86286645,Dodoh Receives Party Wheel,,-,-
052801C5A785CEDD5CB411EDDE9095AB,The End,,-,-
05324A4E5A65A1242FD4F961A663D5FD,Sky Keep Intro Room,,0:00:00,0:00:00
06FC63FA3986951002602E703B0E9CD7,Lanayru's Vocals,,-,-
07B5A2222997D394DC7602A61A8F6883,Koloktos,,0:00:00,0:00:00
...
```