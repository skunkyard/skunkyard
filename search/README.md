# Search demo

The smallest working site search: three pages and a search page, indexed by
[Pagefind](https://pagefind.app/). No server, no database, no build tool beyond
one command. It's the same setup as the search on
[skunkyard.com](https://skunkyard.com/search/); the write-up is at
[skunkyard.com/experiments/site-search/](https://skunkyard.com/experiments/site-search/).

| file | what it is |
|---|---|
| `a.html`, `b.html`, `c.html` | Three pages. Every word on each starts with its letter. |
| `index.html` | The search page: Pagefind's input, summary, and results components. |

## Try it

You need Node.js. From this folder:

```bash
npx -y pagefind@1.6.0 --site . --serve
```

Pagefind indexes the three pages into `pagefind/`, then serves the folder at
<http://localhost:1414/>. Search for `aardvark`, `badger`, or `cactus`.

## How it works

- `data-pagefind-body` on each page's `<main>` tells Pagefind what to index.
  Pages without it, such as `index.html`, stay out of the results.
- The index is static files. The browser downloads only the parts a search
  needs, so it stays fast as the site grows.
- On a real site, run the same command (without `--serve`) after the pages are
  built and before they're uploaded.
- With a Content Security Policy, allow `'wasm-unsafe-eval'` in `script-src`
  and `worker-src 'self' blob:`
  ([Pagefind's hosting notes](https://pagefind.app/docs/hosting/)).
