# Hosting the podcast feed + audio on GitHub Pages

Yes — this repo can be its own podcast host, for free, using
**GitHub Pages**. That is the simplest way to give Spotify the two
public HTTPS things it needs: `feed.xml` and the episode MP3s.

## Layout (already in this repo)

GitHub Pages is enabled with source = **main branch, `/docs` folder**:

| File | URL once Pages is on |
|---|---|
| `docs/index.html` | `https://pivital-az.github.io/oloj-homily-automation/` |
| `docs/feed.xml` | `https://pivital-az.github.io/oloj-homily-automation/feed.xml` |
| `docs/audio/<episode>.mp3` | `https://pivital-az.github.io/oloj-homily-automation/audio/<episode>.mp3` |
| `docs/.nojekyll` | Tells Pages to serve files as-is (no Jekyll build) |

The human page is incidental — the important visitors are Spotify /
Apple, which read `feed.xml` and stream the MP3s it points to.

## Enable it (once, 2 minutes, in a browser)

1. Repo → **Settings → Pages**.
2. Build and deployment → Source: **Deploy from a branch** →
   Branch: **main**, Folder: **/docs** → Save.
3. Wait for the "Your site is live" banner, open the `feed.xml` URL
   above and confirm you see XML.

## Configure the pipeline for it (.env)

```ini
ENABLE_SPOTIFY=true
PODCAST_AUDIO_DIR=.\docs\audio
PODCAST_FEED_FILE=.\docs\feed.xml
PODCAST_AUDIO_BASE_URL=https://pivital-az.github.io/oloj-homily-automation/audio
PODCAST_FEED_BASE_URL=https://pivital-az.github.io/oloj-homily-automation
PODCAST_ARTWORK_URL=<public URL of 1400x1400 to 3000x3000 JPG/PNG>
```

After each pipeline run: `.\scripts\publish_pages.ps1`
(commits + pushes `docs\audio` and `docs\feed.xml`).

Then submit the feed URL **once** in Spotify for Podcasters —
see `SPOTIFY.md`. New episodes appear automatically after that.

## Capacity — read this before committing to it forever

GitHub's documented limits: **published Pages sites may be no larger
than 1 GB**, source repos have a **recommended limit of 1 GB**, and
Pages has a **soft bandwidth limit of 100 GB/month**.

Homily clips from this pipeline are mono, 128 kbps ≈ **0.96 MB/min**:

| Homily length | File size | Episodes in ~1 GB |
|---|---|---|
| 10 min | ~9.6 MB | ~100 |
| 12 min | ~11.5 MB | ~85 |
| 15 min | ~14.4 MB | ~65 |

How long that lasts:

- **1 homily / Sunday:** ~65–100 weeks ≈ **1.5–2 years**
- **3 homilies / Sunday** (all Sunday Masses): ~22–33 weeks ≈ **5–8 months**

Bandwidth is not the problem: 100 GB/month ÷ ~11.5 MB ≈ **8,500 plays
a month**, far more than a parish podcast will use.

Two traps to know about:

1. **Git history never shrinks.** Deleting old MP3s frees Pages space
   but the files stay in git history, so the repo keeps growing and
   clones/pushes get slower. Treat ~700 MB of audio as the migration
   trigger, not 1 GB.
2. **The feed URL is the podcast's identity.** Submitting the
   `github.io` URL to Spotify and later moving hosts means a feed
   migration. If the parish can add one DNS record, point a custom
   domain at Pages from day one (Settings → Pages → Custom domain:
   `podcast.oloj.org`, a CNAME to `pivital-az.github.io`). Then the
   feed lives at `https://podcast.oloj.org/feed.xml` forever, and the
   files behind it can move to S3 / Cloudflare R2 later without
   listeners or Spotify ever noticing.

## Verdict

GitHub Pages is a **good free starting host** for this project:
zero cost, zero new accounts, fully automatable from the laptop.
Plan on it for roughly the first year (or first ~5–8 months if every
Sunday Mass is published), and move the audio — not the feed URL —
to cheap object storage when the repo approaches ~700 MB.
