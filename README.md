# SSR Custom Music Automation

Skyward Sword Randomizer supports custom music packs. Creating one is relatively annoying,
as you need to pay attention to various details like number of streams or looping status,
manually input values into janky GUIs, and rename/copy a bunch of files.

This project is an attempt to automate these menial tasks and improve maintainability of music packs.

This basically automates a lot of steps in CovenEsme's (fantastic) [Custom Music Written Tutorial](https://docs.google.com/document/d/1OHyxV5rZx8YuqXsf5ewp3qPz7-rpLSoRjyl3gg4fSJU/edit?usp=sharing) --
you should probably read that document first to understand what this tool is actually doing.

## Elevator Pitch

Run `convert.py new shovel_knight`, fill out the song data in `./shovel_knight/music.csv`, run `convert.py patch ./shovel_knight`,
start the game in Dolphin, and you're done.

```csv
Id,Name,Source,Loop Start,Loop End,Volume Adjustment,Delay,Override Streams
AD8CEDF96286EF95A49E3469720E2373,File Select 1,Steel Thy Shovel,0:00.191,0:42.861,,,
BCAF01802B2AF3E03778255F2CE7CFD5,File Select 2,$File Select 1,0:00.000,0:00.000,,,
CB6F555F49167EB4545ACC3DF6AEE55F,File Select Music During Cutscene after Sky Keep,$File Select 1,0:00.000,0:00.000,,,
B4398B07F3EC7009C2214515AED0CEA4,Final Demise,The Betrayer (Enchantress Final Form),0:45.284,2:31.239,,,
C47D3DF4C435739443D195F7265A7D57,Game Over,Dealt a Setback,-,-,,,
...
```

## Detailed Instructions

1. Clone or download this tool.
1. Download [VGAudioCLI](https://github.com/Thealexbarney/VGAudio/releases) and place its executable in the tool directory (right next to this Readme).
1. Install ffmpeg somewhere.
1. Install `toml` and `yaml` e.g. via pip, conda, whatever
1. Create a copy of `config.toml.template` named `config.toml` and fill out the data.
1. Create a new project with `python convert.py new my_project_name`
1. Fill out the `./my_music_name/music.csv` sheet with the song data.
1. Run `python convert.py build my_project_name` to build the project.
1. Run `python convert.py patch my_project_name` to patch your built project into the ssrando directory.
1. Run `python convert.py dist my_project_name` to create a redistributable zip file in `./my_project_name/dist/my_project_name.zip` that others can extract into their ssrando installation to use your music.

## CSV Column Headers

* **Id**: The internal track ID. Do not change, ever!
* **Name**: The human-readable name from the music.yaml. Feel free to rename if a name is confusing :p
* **Source**: A fragment of the OST file name in a subdirectory of the `ost` paths in `config.toml`
* **Loop Start**/**Loop End**: For looping songs, `mm:ss.s` timestamps of loop start and end. Audacity with loop markers can help coming up with a clean loop.
* **Volume adjustment**: A volume scalar (as defined by an ffmpeg scalar, not a dB value) applied to the track.
* **Delay**: Music start is delayed by this many milliseconds. Note that this shifts the Loop Start/End times! (TODO this should be changed?)
* **Override Streams**: Some tracks have multiple streams where some are only conditionally active (e.g. Boko base: Stream 1 always, Stream 2 when not near enemies, Stream 3 when near enemies). Set to 1 so that only the always active stream is used and the rest is silence. (TODO this is a kludge and should probably be replaced by a better data source?)

Sometimes there are tracks with multiple copies that basically do the same thing (File Select 1 / File Select 2).
In that case you can fill out details for File Select 1 and just put `$File Select 1` in the name of File Select 2 -
this causes File Select 2 to copy all data from File Select 1.