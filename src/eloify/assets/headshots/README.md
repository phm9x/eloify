# Player headshots (braille)

One file per player, named after their **username** (the name `elo players`
shows), e.g. `duncan.txt`. Each holds a small braille rendering of the player's
photo and is what gets displayed by `elo history` and `elo headshot <name>`.

**Only these `.txt` files are committed — never the photos.** The source images
are face-cropped to 512px squares and kept in the git-ignored `headshots/`
folder at the repo root.

## Adding one

Let the CLI fetch, face-crop, render, and write the `.txt` for you. Needs the
Python extra (`pip install 'eloify[headshots]'` → Pillow + OpenCV) and the
`chafa` binary for the braille rendering (`brew install chafa`):

```bash
elo set-headshot <username> ~/Pictures/whoever.jpg
elo set-headshot <username> https://example.com/whoever.png
```

Then commit the new `src/eloify/assets/headshots/<username>.txt`.

## Still missing a headshot

These registered players don't have one yet — add when you find a photo:

- `derek`
