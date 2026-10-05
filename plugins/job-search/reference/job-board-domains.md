# Job-board domains

These are the sites the engine reads, for setup's network step. When Claude's network setting can list specific sites, add these. Otherwise the user has to choose "All domains".

```
boards-api.greenhouse.io
api.ashbyhq.com
api.lever.co
api.smartrecruiters.com
*.myworkdayjobs.com
api.rippling.com
himalayas.app
www.atlassian.com
jobs.intuit.com
www.github.careers
careers.docusign.com
```

| Site | Used for |
|---|---|
| `boards-api.greenhouse.io` | Greenhouse boards (311 of the 589 starter boards) |
| `api.ashbyhq.com` | Ashby boards (171) |
| `api.lever.co` | Lever boards (61) |
| `*.myworkdayjobs.com` | Workday boards (28). Each company has its own address under this domain, such as `acme.wd5.myworkdayjobs.com`, so the entry needs the `*.` |
| `api.smartrecruiters.com` | SmartRecruiters boards (12) |
| `api.rippling.com` | Rippling boards (2) |
| `himalayas.app` | The Himalayas remote-jobs search, when the user's field pack uses it |
| `www.atlassian.com`, `jobs.intuit.com`, `www.github.careers`, `careers.docusign.com` | Four companies' own careers sites |

A company added later with `discover` uses one of the first six sites, so the list rarely changes.

Claude's own web fetch, used to read a job link the user pastes, doesn't need any of this: the network setting doesn't apply to it.
