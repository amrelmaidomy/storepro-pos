import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import sys


def main():
    parser=argparse.ArgumentParser(description='StorePro offline POS')
    parser.add_argument('--data-dir',type=Path,default=Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'StorePro')
    parser.add_argument('--import-legacy',type=Path,help='Import original storepro.db before first run')
    args=parser.parse_args(); args.data_dir.mkdir(parents=True,exist_ok=True)
    if args.import_legacy:
        destination=args.data_dir/'storepro.db'
        if destination.exists(): parser.error('Data already exists. Choose an empty --data-dir.')
        if not args.import_legacy.is_file(): parser.error('Legacy database not found.')
        shutil.copy2(args.import_legacy,destination)
    handler=RotatingFileHandler(args.data_dir/'errors.log',maxBytes=1000000,backupCount=3,encoding='utf-8')
    logging.basicConfig(handlers=[handler],level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    try:
        from storepro.ui.app import App
        App(args.data_dir).run()
    except Exception:
        logging.exception('Startup failed')
        print('StorePro failed to start. See errors.log in the data directory.',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__': raise SystemExit(main())
