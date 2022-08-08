import fire
import json
import logging
import os

logger = logging.getLogger(__name__)

def main(games_path, offset, dry_run=True):
    logging.basicConfig(level=logging.INFO)
    # Game folder file format:
    # {date}_{game id}_{game type}
    # For each file in the path, extract the game ID number. Add offset to it.
    # Then open the game_info.jsonl.log file and update the following fields:
    # "game_id": game_id + offset,
    # "game_name": {date}_{game id + offset}_{game type}

    # For each file in games_path...
    game_folders = list(os.listdir(games_path))
    for folder in game_folders:
        # Ignore .DS_Store file
        if folder == '.DS_Store':
            continue
        # Extract the game ID number from the file name.
        old_game_id = int(folder.split('_')[1])
        # Add offset to the game ID number.
        new_game_id = old_game_id + offset

        (date, game_id, game_type) = folder.split('_')

        # Open the game_info.jsonl.log file. It's a 1-line JSON file. Modify the fields.
        with open(os.path.join(games_path, folder, 'game_info.jsonl.log'), 'r') as f:
            game_info = json.load(f)
            (date, game_name_id, game_type) = game_info['game_name'].split('_')
            game_name_id = int(game_name_id)
            if game_name_id != game_info['game_id']:
                logger.warn(f"game_name_id ({game_name_id}) != game_id ({game_info['game_id']})")
            if game_info['game_id'] != old_game_id:
                logger.warn(f"game_id ({game_info['game_id']}) != old_game_id ({old_game_id})")
            game_info['game_id'] = new_game_id
            game_info['game_name'] = '{}_{}_{}'.format(date, new_game_id, game_type)
        
        # Write the modified game_info.jsonl.log file.
        if not dry_run:
            with open(os.path.join(games_path, folder, 'game_info.jsonl.log'), 'w') as f:
                json.dump(game_info, f)

        # Rename the folder.
        if not dry_run:
            os.rename(os.path.join(games_path, folder), os.path.join(games_path, '{}_{}_{}'.format(date, new_game_id, game_type)))


if __name__ == "__main__":
    fire.Fire(main)