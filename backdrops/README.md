# Album colours for Spotish

`make_backdrops.py` gives every album its own Spotify-style glow on the Now Playing screen.

A Rockbox theme can't read colours out of album art, so this script does it once on your
computer. For each album on the iPod it draws a 320x240 picture (a dark blur of the cover's own
colours with the rounded cover on top) and saves it next to the music as `cover.320x240.bmp`.
Rockbox looks for a cover made for the exact size a theme asks for before the normal one, so
Spotish shows it automatically. Your own covers and music are never changed.

## Use

1. Install Python 3 and the two helpers: `pip install pillow mutagen`
2. Connect the iPod (disk mode) and run: `python make_backdrops.py`
   It finds the iPod by itself. You can also give the place: `python make_backdrops.py E:\`
   on Windows, `python make_backdrops.py /Volumes/IPOD` on a Mac.
3. Run it again whenever you add music. Albums that are already done are skipped.

Options: `--dry-run` shows what it would do, `--force` remakes everything, `--remove` deletes
exactly the files it made (listed in `.rockbox/spotish-backdrops.txt`).

## Where the art comes from

The same places Rockbox uses with *album art: prefer image file* (Spotish turns that on):
an image named after the track, then `cover.jpg` / `folder.jpg` in the folder, then the parent
folder's `cover.jpg` (multi-disc albums), then art embedded in the songs (needs `mutagen`).
A folder of singles with different art gets one picture per song.

Each picture is about 225 KB, so 1,000 albums take about 225 MB.
