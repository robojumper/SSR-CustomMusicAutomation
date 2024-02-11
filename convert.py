from datetime import datetime
import os
from os import path
from pathlib import Path
import shutil
import subprocess
import toml
import yaml

def load_config():
    return toml.load('./config.toml')

def make_ost_index(config):
    index = []
    for f in os.listdir(config['ost']):
        f = path.join(config['ost'], f)
        index.append({ 'name': Path(f).stem, 'path': f })
    return index

def ffmpeg(in_file_name, tmp_file_name, num_streams):
    num_channels = num_streams * 2
    repeatspec = '[0:a]' * num_channels
    subprocess.call([
        'ffmpeg',
        '-y',
        '-i',
        in_file_name,
        '-filter_complex',
        f'{repeatspec}amerge=inputs={num_channels}[a]',
        '-map',
        '[a]',
        tmp_file_name,
    ])

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

def load_project():
    project_index = {}
    for f in os.listdir('./shovel_knight'):
        f = path.join('./shovel_knight', f)
        data = toml.load(f)
        project_index[Path(f).stem.lower()] = { 'data': data, 'mtime': path.getmtime(f), 'used': False }
    return project_index

def load_music_yaml(config):
    yaml_path = path.join(config['music_yaml'], 'music.yaml')
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.load(f, Loader=yaml.CSafeLoader)

def main():
    config = load_config()
    music = load_music_yaml(config)
    project = load_project()
    ost = make_ost_index(config)

    os.makedirs('./tmp/shovel_knight', exist_ok=True)

    for id, gamedata in music.items():
        name = gamedata['name'].lower()
        spec = None
        if id in project and name in project:
            print(f'Warning: {id} and {name} refer to the same music file, using {name}')
            spec = project[name]
        elif id in project:
            spec = project[id]
        elif name in project:
            spec = project[name]

        # print(id, name, userdata)

        if spec:
            spec['used'] = True
            userdata = spec['data']
            if not 'source' in userdata:
                print(f'Error: track {name}/{id} has no source')
                continue
            source_pattern = userdata['source']
            applicable_source_files = [obj for obj in ost if source_pattern in obj['name']]
            if not applicable_source_files or len(applicable_source_files) > 1:
                print(f'Error: pattern {source_pattern} matches too many files')
                continue
            tmpfile = path.join('./tmp', 'shovel_knight', f'{id}.wav')
            num_streams = gamedata['streams']
            if not path.exists(tmpfile) or path.getmtime(tmpfile) < spec['mtime']:
                ffmpeg(applicable_source_files[0]['path'], tmpfile, num_streams)

            outfile = path.join('./tmp', 'shovel_knight', f'{id}.brstm')
            if not path.exists(outfile) or path.getmtime(outfile) < spec['mtime']:
                if gamedata['isLooped']:
                    if 'loopstart' not in userdata or 'loopend' not in userdata:
                        print(f'Error: track {name}/{id} has no loop start/end')
                        continue
                    outfile = path.join('./tmp', 'shovel_knight', f'{id}.brstm')
                    vgcli_loop(tmpfile, outfile, num_streams, userdata['loopstart'], userdata['loopend'])

            target_file = path.join(config['ssrando'], 'modified-extract', 'DATA', 'files', 'Sound', 'wzs', id)
            if not path.exists(target_file) or path.getmtime(target_file) != path.getmtime(outfile):
                shutil.copyfile(outfile, target_file)

    for name, spec in project.items():
        if not spec['used']:
            print(f'Warning: {name} not used')



if __name__ == '__main__':
    main()