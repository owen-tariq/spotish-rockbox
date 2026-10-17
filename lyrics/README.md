# Spotify-style synced lyrics for Rockbox (iPod Video)

Rockbox ships a plugin, **lrcplayer**, that shows synced lyrics while a song plays.

## 1. Spotify-style look

Copy `lrcplayer.cfg` to `.rockbox/rocks/apps/lrcplayer.cfg` on the iPod. It sets:
upcoming lines grey and sung lines white, left aligned, whole lines (no karaoke wipe), no title or time
(the Spotish mini player shows those), and lyrics drawn inside the theme's card.

## 2. Open it from Now Playing

On the iPod Video, a **short press of the centre button** on Now Playing runs the "hotkey". Set
**Settings → General Settings → System → Hotkey → WPS Hotkey** (wording varies by build) to
**Open plugin**, and choose `lrcplayer` if asked. Press **Menu** to go back.

## 3. Get lyrics for your own music

`fetch_lyrics.py` reads your music's tags, asks [LRCLIB](https://lrclib.net) for **synced** lyrics
(matching title, artist, album and length), and saves `.lrc8` files (UTF-8) where lrcplayer finds them.

```
pip install requests mutagen
python fetch_lyrics.py E:\Music          # path to the Music folder on the iPod
```

Then copy the contents of the generated `ipod/` folder onto the iPod's root.

Notes:

- **Where files go:** flat in `/Lyrics/<song file name>.lrc8`. (Builds with multivolume support use paths
  like `/<HDD0>/Music/...`, which breaks lrcplayer's mirrored-folder lookup; the flat folder always
  works.) Songs whose file names clash get a `Lyrics` folder next to the song instead.
- **Songs without lyrics** get a one-line "Lyrics aren't available for this song" file, because lrcplayer
  shows a blank screen when it finds nothing.
- **Fonts:** Rockbox fonts usually only cover Latin, Greek and Cyrillic, so Devanagari, Gurmukhi and Tamil
  lyrics are romanised (approximate spelling) and typographic punctuation is turned into ASCII. Lyrics only
  available in Urdu/Arabic script are skipped.
- **Privacy & etiquette:** it sends song titles/artists to lrclib.net, waits between requests, and keeps a
  log (`lyrics_log.csv`) so reruns only look up new songs. Lyrics are copyrighted — keep them for personal
  use and don't redistribute them.
