import argparse
import csv
from datetime import datetime
import os
from os import path
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZipFile
import toml
import yaml

config = None

def load_config():
    global config
    if not config:
        config = toml.load('./config.toml')
    return config


def make_ost_index():
    config = load_config()
    index = []
    ost = config['ost']
    if type(ost) != list:
        ost = [ost]
    for dir in ost:
        for base_path, _directories, files in os.walk(dir):
            for file in files:
                f = path.join(base_path, file)
                index.append({ 'name': Path(f).stem, 'path': f })
    return index

def ffmpeg(in_file_name, tmp_file_name, num_streams, volume=None, delay=None, override_streams=None):
    num_total_channels = num_streams * 2
    num_audio_channels = (override_streams or num_streams) * 2
    num_silent_channels = num_total_channels - num_audio_channels

    audio_channel_spec = ''.join(map(lambda i: f'[s{i}]', range(0, num_audio_channels)))
    silent_channel_spec = '[1:a]' * num_silent_channels

    args = [
        'ffmpeg',
        '-y',
        '-i',
        in_file_name,
        '-f',
        'lavfi',
        '-i',
        'anullsrc=channel_layout=mono:sample_rate=44100',
        '-filter_complex',
        f'[0:a]volume={volume or 1}, adelay=delays={delay or 0}:all=1, asplit={num_audio_channels}{audio_channel_spec}; {audio_channel_spec}{silent_channel_spec}amerge=inputs={num_total_channels}[o]',
        '-map',
        '[o]',
        tmp_file_name,
    ]
    print(args)
    subprocess.call(args)

def time_to_samples(t):
    a = datetime.strptime(t, '%M:%S.%f')
    t = a.minute * 60 + a.second + a.microsecond / 1e6
    samples = int(t * 44100)
    return samples

def vgcli_loop(tmp_file_name, out_file_name, num_streams, loop_start, loop_end):
    num_channels = num_streams * 2
    subprocess.call([
        'VGAudioCli',
        '-c',
        f'-i:0-{num_channels-1}',
        tmp_file_name,
        '-l',
        f'{time_to_samples(loop_start)}-{time_to_samples(loop_end)}',
        '-o',
        out_file_name
    ])

def vgcli_noloop(tmp_file_name, out_file_name, num_streams):
    num_channels = num_streams * 2
    subprocess.call([
        'VGAudioCli',
        '-c',
        f'-i:0-{num_channels-1}',
        tmp_file_name,
        '-o',
        out_file_name
    ])

def load_music_yaml() -> dict:
    config = load_config()
    yaml_path = path.join(config['music_yaml'], 'music.yaml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.load(f, Loader=yaml.CSafeLoader)
    
def resolve(index, id, name: str):
    if id in index:
        return index[id]
    elif name in index:
        return index[name]
    else:
        short_name = re.sub('\s*[0-9]+$', '', name)
        if short_name in index:
            return index[short_name]
        
COLUMNS = ['Id', 'Name', 'Source', 'Loop Start', 'Loop End', 'Volume Adjustment', 'Delay', 'Override Streams']
        
def new_project(name: str):
    if path.exists(f'./{name}'):
        print(f'error: directory {name} already exists')
        exit(1)

    os.makedirs(f'./{name}')
    music_yaml = load_music_yaml()
    rows = []
    for id, gamedata in music_yaml.items():
        looped = gamedata['isLooped']
        loop_timespec = '0:00.000' if looped else '-'
        rows.append([id, gamedata['name'], '', loop_timespec, loop_timespec, None])

    rows.sort(key = lambda row: row[1])
    rows.insert(0, COLUMNS)
    with open(f'./{name}/music.csv', 'w', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows)

def get_project(name: str, all=False):
    if not path.exists(f'./{name}/music.csv'):
        print(f'error: {name} is not a project')
        exit(1)
    songs = {}
    with open(f'./{name}/music.csv', 'r', encoding='utf-8', newline='') as csvfile:
        cols = next(csvfile)
        has_volume = 'Volume Adjustment' in cols
        has_delay = 'Delay' in cols
        has_override_streams = 'Override Streams' in cols
        reader = csv.reader(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in reader:
            if row[2] != "" or all:
                songs[row[0]] = {
                    "name": row[1],
                    "source": row[2],
                    "loopstart": row[3],
                    "loopend": row[4],
                    "volume": float(row[5]) if has_volume and row[5] != '' else None,
                    "delay": int(row[6]) if has_delay and row[6] != '' else None,
                    "streams_override": int(row[7]) if has_override_streams and row[7] != '' else None,
                }
    return songs

def migrate_project(name: str):
    project = get_project(name, True)
    rows = [COLUMNS]
    for id, song in project.items():
        rows.append([id, song['name'], song['source'], song['loopstart'], song['loopend'], song['volume'], song['delay'], song['streams_override']])
    with open(f'./{name}/music.csv', 'w', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows)

def build_project(name: str):
    config = load_config()
    project = get_project(name)
    music = load_music_yaml()
    ost = make_ost_index()
    tmpdir = f'./{name}/tmp'
    os.makedirs(tmpdir, exist_ok=True)

    handled_ids = []

    for id, data in project.items():
        if not id in music:
            print(f'error: unknown id {id}')
            continue

        source = data['source']
        while source.startswith('$'):
            data = next((x for x in project.values() if x['name'] == source[1:]), None)
            if not data:
                print(f'error: source redirection {source} not found')
                continue
            source = data['source']
        
        applicable_source_files = [obj for obj in ost if source in obj['name']]
        if not applicable_source_files:
            print(f'error: pattern {source} matches no files')
            continue
        if len(applicable_source_files) > 1:
            print(f'error: pattern {source} matches too many files')
            continue

        source_file = applicable_source_files[0]['path']
        source_mtime = path.getmtime(source_file)
        streams = music[id]['streams']

        expected_wav_fingerprint = f'{source_file}-{source_mtime}'

        loopstart = data['loopstart']
        loopend = data['loopend']
        vol = data['volume']
        delay = data['delay']
        override_streams = data['streams_override']
        expected_brstm_fingerprint = f'{expected_wav_fingerprint}-{loopstart}-{loopend}-{vol}-{delay}-{override_streams}'
        brstm_fingerprint_file = path.join(tmpdir, f'{id}.brstm.fingerprint')
        rebuild_brstm = False
        brstm_file = path.join(tmpdir, f'{id}.brstm')
        if not path.exists(brstm_file) or not path.exists(brstm_fingerprint_file):
            rebuild_brstm = True
        elif Path(brstm_fingerprint_file).read_text() != expected_brstm_fingerprint:
            rebuild_brstm = True

        wav_file = path.join(tmpdir, f'{id}.wav')
        
        if rebuild_brstm:
            wav_fingerprint_file = path.join(tmpdir, f'{id}.wav.fingerprint')
            rebuild_wav = False
            if rebuild_brstm and not path.exists(wav_file):
                # the brstm needs to be built and the WAV doesn't exist - definitely rebuild
                rebuild_wav = True
            elif not path.exists(wav_fingerprint_file):
                # the WAV fingerprint doesn't exist, so we can't tell if it's up to date
                rebuild_wav = True
            elif Path(wav_fingerprint_file).read_text() != expected_wav_fingerprint:
                # the WAV fingerprint is wrong - must rebuild 
                rebuild_wav = True

            try:
                if rebuild_wav:
                    ffmpeg(source_file, wav_file, streams, vol, delay, override_streams)
                    Path(wav_fingerprint_file).write_text(expected_wav_fingerprint)

                if music[id]['isLooped']:
                    vgcli_loop(wav_file, brstm_file, streams, loopstart, loopend)
                else:
                    vgcli_noloop(wav_file, brstm_file, streams)
                Path(brstm_fingerprint_file).write_text(expected_brstm_fingerprint)
            except Exception as e:
                print('error handling ' + id + ' ' + str(e))
                continue

        if not config['keep_wav'] and path.exists(wav_file):
            os.remove(wav_file)

        handled_ids.append(id)
    return handled_ids

def patch_project(name: str):
    handled_ids = build_project(name)

    music_yaml = load_music_yaml()
    for id in music_yaml.keys():
        target_file = path.join(config['ssrando'], 'modified-extract', 'DATA', 'files', 'Sound', 'wzs', id)

        if id in handled_ids:
            source_file = f'./{name}/tmp/{id}.brstm'
            if path.getmtime(source_file) != path.getmtime(target_file):
                shutil.copyfile(source_file, target_file)
        else:
            # reset all other files
            pristine_file = path.join(config['ssrando'], 'actual-extract', 'DATA', 'files', 'Sound', 'wzs', id)
            if path.getmtime(pristine_file) != path.getmtime(target_file):
                shutil.copyfile(pristine_file, target_file)

def dist_project(name: str):
    handled_ids = build_project(name)

    music_yaml = load_music_yaml()

    tmpdir = f'./{name}/dist'
    os.makedirs(tmpdir, exist_ok=True)
    with ZipFile(path.join(tmpdir, f'{name}.zip'), 'w') as zip:
        for id in music_yaml.keys():
            if id in handled_ids:
                source_file = f'./{name}/tmp/{id}.brstm'
                target_file = path.join('modified-extract', 'DATA', 'files', 'Sound', 'wzs', id)
                zip.write(source_file, target_file)

def main():
    parser = argparse.ArgumentParser(
                prog='SSRMusicAutomation',
                description='A tool for creating and managing custom music packs in Skyward Sword Randomizer')
    subparsers = parser.add_subparsers(dest='command', required=True)
    new = subparsers.add_parser('new', help='Create a new project.')
    new.add_argument('name')

    build = subparsers.add_parser('build', help='Build a project. Useful for verifying that the project is valid, consistent, and/or complete.')
    build.add_argument('name')

    patch = subparsers.add_parser('patch', help='Build a project and patche the SSR modified-extract directory with the generated files.')
    patch.add_argument('name')

    dist = subparsers.add_parser('dist', help='Build a project and create a distributable archive.')
    dist.add_argument('name')

    migrade = subparsers.add_parser('migrate', help='Migrate a project CSV to have all columns.')
    migrade.add_argument('name')

    clean = subparsers.add_parser('clean', help='Clean up all temporary files.')
    clean.add_argument('name', nargs='?')


    args = parser.parse_args()
    print(args)

    if args.command == 'new':
        new_project(args.name)
    elif args.command == 'build':
        build_project(args.name)
    elif args.command == 'patch':
        patch_project(args.name)
    elif args.command == 'migrate':
        migrate_project(args.name)
    elif args.command == 'dist':
        dist_project(args.name)


if __name__ == '__main__':
    main()