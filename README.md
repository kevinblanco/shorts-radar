# shorts-radar

Find the YouTube Shorts that beat their own channel in any niche, then let an AI agent turn them into Short proposals you can shoot.

Ask a chat model what Shorts to make and you get the list everyone gets: it can't see what's on YouTube today. This repo gives it that data in two halves:

1. **A pipeline** (`shorts-radar run "ai agents"`) that uses five [SerpApi](https://serpapi.com) engines to find the Shorts in a niche, judge each one against its own channel, and save the result as JSON.
2. **An agent** (`shorts-strategist`) for Claude Code or any MCP client. It reads that JSON, re-checks the top Shorts live through the [SerpApi MCP server](https://github.com/serpapi/serpapi-mcp), and writes three Short proposals, a one-page brief, and a niche snapshot, citing the Shorts behind every idea.

A real run is in [`examples/ai-agents/snapshot.md`](examples/ai-agents/snapshot.md) (October 25, 2026). Its top three:

| Short | Channel | Views | × its channel | Score |
|---|---|---|---|---|
| [RoadMap to learn Agentic AI](https://www.youtube.com/shorts/a-1lZvvTNOs) | The DotNet Office | 1.8M | 1602× | 86 |
| [How to Build your First AI Agent in 1 Minute](https://www.youtube.com/shorts/g1t_hmndPdo) | Noble Hacks Academy | 1.2M | 321× | 83 |
| [Agentic AI with Java : Live Cohort](https://www.youtube.com/shorts/2gLHiQsbI80) | Telusko | 5.9M | 105× | 71 |

## Run the pipeline

Python 3.11 or newer.

```bash
git clone https://github.com/kevinblanco/shorts-radar
cd shorts-radar
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env          # add your key from serpapi.com/manage-api-key
shorts-radar run "ai agents"
```

It prints each SerpApi call as it happens, with a running count, then a table of the top Shorts. The run is saved to `data/ai-agents/shorts.json` (for the agent) and `data/ai-agents/snapshot.md` (for you). `shorts-radar show "ai agents"` prints a saved run again without spending anything.

| Step | SerpApi engine | Searches (default) |
|---|---|---|
| What people search on YouTube around the topic | [Google Trends](https://serpapi.com/google-trends-api), `gprop=youtube`, related queries | 1 |
| The Shorts YouTube shows for each of those searches | [YouTube Search](https://serpapi.com/youtube-search-api) (`shorts_results`) | 5 |
| Exact views, likes, publish date and channel size for the top 20 | [YouTube Video](https://serpapi.com/youtube-video-api) | 20 |
| Each channel's typical Short, from its recent Shorts | [YouTube Channel](https://serpapi.com/youtube-channel-api), `tab=shorts` | 10 |
| The opening lines of the top 3, word for word | [YouTube Video Transcript](https://serpapi.com/youtube-video-transcript) | 3 to 6 |

A run spends at most 42 searches (`--estimate` prints it for your settings), and every response is cached in `data/cache`, so a second run over the same searches costs nothing. SerpApi's [free plan](https://serpapi.com/pricing) has 250 searches a month. `--keywords`, `--details`, `--channels` and `--hooks` set each step's budget; `--refresh` ignores the cache.

## How a Short is scored

Raw views mostly measure how big a channel is. A million views from a channel with ten million subscribers is an ordinary day. So each Short gets three measures:

- **× its channel**: views divided by the median views of that channel's recent Shorts
- **views per day** since it was posted
- **views per subscriber**

Each measure becomes a percentile within the run, and the radar score (0 to 100) is their average. A Short is scored only once it has been judged against its own channel. High on all three means a pattern worth studying.

## Connect the agent

**Claude Code.** The repo ships a [`.mcp.json`](.mcp.json) that points at SerpApi's hosted MCP server and reads your key from the environment, plus the [`shorts-strategist`](.claude/skills/shorts-strategist/SKILL.md) skill. Claude Code reads the key from your shell, not from `.env`:

```bash
export SERPAPI_API_KEY=your_key
claude
```

Approve the `serpapi` server when asked, then ask: *"What Shorts should I make next in ai agents?"* The agent reads `data/ai-agents/shorts.json`, re-checks the top 8 live (8 searches), and writes three proposals. Pick one and it writes the brief.

Prefer to add the server yourself:

```bash
claude mcp add --transport http serpapi https://mcp.serpapi.com/mcp --header "Authorization: Bearer $SERPAPI_API_KEY"
```

**Other MCP clients** (Claude Desktop, Cursor and others): add an HTTP server at `https://mcp.serpapi.com/mcp` with an `Authorization: Bearer <your key>` header, and give the agent [`SKILL.md`](.claude/skills/shorts-strategist/SKILL.md) and its two templates as instructions.

The server exposes one `search` tool for every SerpApi engine, and publishes each engine's parameters at `serpapi://engines/<engine>`, so the agent can reach beyond YouTube when a proposal needs it.

## What it can't tell you

- **Only public data.** Views, likes, dates, subscriber counts and transcripts. Retention, click-through and traffic sources are in YouTube Studio, and only for your own channel.
- **Search shows evergreen hits.** In the sample run, the top 10 had a median age of 362 days. That's why the agent re-checks which are still climbing before it proposes anything.
- **Not every Short has words.** No transcript usually means text on screen or music; the run records it as a visual hook.
- **Trends can wander off topic.** "ai for real estate agents" is related to "ai agents" in Trends' data, but not in meaning. Related searches are kept only when they hold the seed's words close together.
- **An outlier shows what worked once.** Copy the pattern, never the video.

## Project layout

```
src/shorts_radar/
  collect.py   the five engines, in order
  score.py     the three measures and the radar score
  report.py    shorts.json, snapshot.md and the terminal table
  serp.py      SerpApi client: search count, disk cache, key kept out of errors and files
  cli.py       run and show
.claude/skills/shorts-strategist/   the agent's instructions and templates
.mcp.json                           the SerpApi MCP server for Claude Code
examples/ai-agents/                 a real run
tests/                              pytest, with a fake SerpApi client
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The tests run the whole pipeline against a fake client that answers in the shapes SerpApi returned for each engine, so they spend no searches.

## License

MIT
