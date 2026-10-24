# super-duper-downloader

**English** · [Русский](README.ru.md)

A work-in-progress pet downloader that can download almost (no) anything.

Paste a link, get the file. A self-hosted web downloader for public media: YouTube,
TikTok, Instagram, X, VK, SoundCloud and the rest of the
[sites yt-dlp supports](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md),
plus plain file links.

- One link shows a preview and only the qualities the media really has: best, 1080p,
  720p, 480p or audio, each with its approximate size where the site gives enough to
  tell. A quality is measured on the shorter side, so 720p of a vertical video is
  720x1280. Video comes as H.264 with AAC where the site offers it, so it plays
  everywhere.
- Audio is the site's own sound track. Where a site has none apart from the video, the
  sound is copied out of the video without re-encoding.
- Bulk mode takes up to 50 links at once, pasted or loaded from a `.txt`, and offers
  the whole batch as a zip.
- Playlists expand into separate downloads, while a post with several videos, such as
  an Instagram carousel, comes as one download with a file per video. Progress streams
  live, and the list of downloads survives a page reload.
- A terminal-style interface in Russian or English, with 23 color themes and four
  monospace fonts.

## What it downloads, and what it does not

Tried in October 2026 from a hosting and VPN address. Every mark below is a file that
was downloaded through the app and checked with ffprobe.

| Site | Video | Audio | Note |
| --- | :---: | :---: | --- |
| YouTube: videos, Shorts, Music | ✓ | ✓ | |
| TikTok, photo slideshows too | ✓ | ✓ | Audio is the post's sound, which can run longer than the video |
| Instagram: reels, posts, carousels | ✓ | ✓ | |
| X | ✓ | ✓ | |
| VK | ✓ | ✓ | |
| Rutube | ✓ | ✓ | |
| OK.ru | ✓ | ✓ | |
| Facebook reels | ✓ | — | The reel tried had no sound |
| Pinterest | ✓ | ✓ | |
| Bluesky | ✓ | ✓ | |
| Twitch clips | ✓ | ✓ | |
| Kick clips | ✓ | ✓ | |
| Dailymotion | ✓ | ✓ | |
| Streamable | ✓ | ✓ | |
| Imgur | ✓ | — | GIF videos have no sound |
| Snapchat Spotlight | ✓ | ✓ | |
| Telegram, public posts | ✓ | ✓ | |
| Tumblr | ✓ | ✗ | The site rate-limited the audio attempt |
| SoundCloud: tracks, sets | — | ✓ | |
| Bandcamp | — | ✓ | |
| Mixcloud | — | ✓ | |
| Plain file links | ✓ | ✓ | |

✓ works, ✗ failed, — nothing to download.

- **Refused that address:** Reddit, Bilibili, Rumble, Vimeo. See
  [Sites that refuse servers](#sites-that-refuse-servers).
- **Need a logged-in account,** which the downloader does not take: Instagram stories,
  Douyin, private and age-restricted videos.

Sites change often, so any of this can break until yt-dlp or cobalt catches up.

## Running it

You need Docker with Compose v2.

```sh
git clone https://github.com/NekitTOP4IK/super-duper-downloader.git
cd super-duper-downloader
cp .env.example .env
docker compose up -d --build
```

The site opens at <http://localhost>. To serve it on a domain, set `SITE_ADDRESS` in
`.env` to that domain: Caddy then gets a certificate on its own, provided ports 80 and
443 are reachable from the internet.

> [!WARNING]
> There are no accounts yet. Anyone who can open the page can download through your
> server, using its bandwidth and disk, held back only by the per-address rate limits
> below. The other limits apply to everyone together.

### Behind another web server

If ports 80 and 443 already belong to a web server such as nginx, publish Caddy on a
local port instead, in a `docker-compose.override.yml` next to `docker-compose.yml`:

```yaml
services:
  caddy:
    ports: !override
      - "127.0.0.1:18090:80"
```

Then proxy the domain to `127.0.0.1:18090` from that server, with response buffering
off (`proxy_buffering off` in nginx): download progress comes as an event stream. Pass
the client address on in `X-Forwarded-For`
(`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`), or all visitors share
one rate limit. Link previews take the site address from `Host` and `X-Forwarded-Proto`,
so pass those on as well.

## Configuration

Everything lives in `.env`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SITE_ADDRESS` | `:80` | Address Caddy serves: `:80` for plain HTTP, or a domain for HTTPS |
| `PROXY_URL` | empty | Proxy for yt-dlp and direct downloads, e.g. `socks5://host:1080` |
| `EGRESS_ALLOW_CIDRS` | empty | Networks workers may reach although they look private, see below |
| `MAX_DURATION_SEC` | `10800` | Longest media accepted |
| `MAX_FILESIZE_MB` | `2048` | Largest file accepted |
| `MAX_BATCH_URLS` | `50` | Links taken from one request |
| `MAX_PLAYLIST_ITEMS` | `50` | Items taken from one playlist |
| `MAX_QUEUE` | `500` | Waiting downloads before new ones are refused |
| `MAX_PROBE_QUEUE` | `100` | Waiting previews before new ones are refused |
| `MIN_FREE_DISK_GB` | `5` | Free space below which new downloads are refused |
| `WORKER_CONCURRENCY` | `3` | Downloads running at once |
| `PROBE_CONCURRENCY` | `10` | Previews running at once |
| `JOB_TIMEOUT_SEC` | `1800` | Time one download may take |
| `FILE_TTL_HOURS` | `6` | How long finished files are kept |
| `RATE_PROBES_PER_MINUTE` | `30` | Previews one address may ask for per minute, `0` for no limit |
| `RATE_DOWNLOADS_PER_HOUR` | `100` | Links one address may send to download per hour, `0` for no limit |

### Sites that refuse servers

Some sites answer hosting and VPN networks with a block page instead of the media.
Reddit sent one to every client tried from such an address, browser imitation included,
and Bilibili, Rumble and Vimeo refused it too. A residential proxy in `PROXY_URL` helps
yt-dlp and plain downloads. cobalt does not read that variable: it takes an HTTP proxy
from `HTTP_PROXY` or `HTTPS_PROXY` set in its own `environment` in `docker-compose.yml`.

## How it works

Caddy serves the interface and passes `/api` to a FastAPI service. Previews and
downloads go through Redis queues to separate workers. A worker tries yt-dlp first,
then [cobalt](https://github.com/imputnet/cobalt) (running as its own container), then
a plain HTTP download for direct file links. If all of them fail, the user sees the
most specific reason, such as "login required". Finished files are deleted after
`FILE_TTL_HOURS`.

## Security notes

Workers open whatever URL a user pastes, so they refuse connections to private,
loopback, link-local and other non-public addresses, including the cloud metadata
endpoint. Redis and cobalt stay reachable for the service's own code, but not for
anything a user URL leads to, redirects included. A few things are outside that guard:

- **`EGRESS_ALLOW_CIDRS`.** Some proxies (Clash, sing-box in fake-ip mode) resolve
  every domain to `198.18.0.0/15`, which then looks private and gets blocked. Listing
  that range fixes downloads, but also makes everything in it reachable for user URLs.
  Only list networks that hold nothing of yours.
- **`PROXY_URL`.** With a proxy, the guard only sees the connection to the proxy, and
  the proxy decides where requests go. Use one that cannot reach your internal network.
- **ffmpeg.** When yt-dlp hands a stream to ffmpeg, ffmpeg connects on its own and is
  not checked.
- **Browser impersonation.** TikTok and some other sites only answer clients that look
  like a browser, so yt-dlp sends those requests through curl_cffi, which connects
  outside Python and is not checked either. Only extractors of specific sites do this,
  for their own hosts, but curl follows up to five redirects from there on its own.

## Development

```sh
docker compose -f docker-compose.dev.yml up -d --build
```

This runs the API on port 8000 and restarts it and the workers when files in
`backend/app` change. Then start the interface, which proxies `/api` to that port:

```sh
cd frontend
npm ci
npm run dev
```

Checks, the same ones CI runs. In `backend`:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run pytest -m network` adds the few tests that talk to real sites. In `frontend`:

```sh
npm test
npm run build
```

## Credits

Downloads are done by [yt-dlp](https://github.com/yt-dlp/yt-dlp),
[cobalt](https://github.com/imputnet/cobalt) and [FFmpeg](https://ffmpeg.org). The
interface builds on [terminal.css](https://github.com/Gioni06/terminal.css) and the
fonts [JetBrains Mono](https://www.jetbrains.com/lp/mono/),
[IBM Plex Mono](https://github.com/IBM/plex),
[Geist Mono](https://github.com/vercel/geist-font) and
[Fira Code](https://github.com/tonsky/FiraCode), served through
[Fontsource](https://fontsource.org).

The color themes follow the palettes of [Tokyo Night](https://github.com/folke/tokyonight.nvim),
[Catppuccin](https://github.com/catppuccin/catppuccin),
[Kanagawa](https://github.com/rebelot/kanagawa.nvim),
[Rosé Pine](https://rosepinetheme.com),
[Everforest](https://github.com/sainnhe/everforest),
[Gruvbox Material](https://github.com/sainnhe/gruvbox-material),
[Nord](https://www.nordtheme.com),
[Oxocarbon](https://github.com/nyoom-engineering/oxocarbon.nvim),
[Dracula](https://draculatheme.com) and [Flexoki](https://stephango.com/flexoki),
adjusted to one contrast range.

## License

[AGPL-3.0](LICENSE).

Download only what you have the right to download.
