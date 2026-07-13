#!/usr/bin/env python3
import os
import requests
from datetime import datetime, date

GITHUB_TOKEN = os.environ["GH_TOKEN"]        # set as a repo secret
USERNAME = os.environ.get("GH_USERNAME", "nattaphom0x")

HEADERS = {"Authorization": f"bearer {GITHUB_TOKEN}"}
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"


def graphql_query(query: str, variables: dict) -> dict:
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def get_basic_stats(username: str) -> dict:
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          nodes { stargazerCount }
        }
        followers { totalCount }
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
        }
      }
    }
    """
    data = graphql_query(query, {"login": username})["user"]
    stars = sum(r["stargazerCount"] for r in data["repositories"]["nodes"])
    commits = (
        data["contributionsCollection"]["totalCommitContributions"]
        + data["contributionsCollection"]["restrictedContributionsCount"]
    )
    return {
        "repos": data["repositories"]["totalCount"],
        "stars": stars,
        "followers": data["followers"]["totalCount"],
        "commits": commits,
    }


def render_svg(stats: dict, theme: str) -> str:
    """theme: 'light' or 'dark'"""
    colors = {
        "dark": {"bg": "#0d1117", "text": "#c9d1d9", "accent": "#58a6ff"},
        "light": {"bg": "#ffffff", "text": "#24292f", "accent": "#0969da"},
    }[theme]

    today = date.today().isoformat()

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="300"
     font-family="Consolas, monospace" font-size="14px">
  <rect width="100%" height="100%" fill="{colors['bg']}" rx="10"/>
  <text x="20" y="35" fill="{colors['accent']}" font-size="18px">{USERNAME}@github</text>
  <line x1="20" y1="45" x2="580" y2="45" stroke="{colors['text']}" stroke-opacity="0.3"/>
  <text x="20" y="75" fill="{colors['text']}">Repos: {stats['repos']}</text>
  <text x="20" y="100" fill="{colors['text']}">Stars: {stats['stars']}</text>
  <text x="20" y="125" fill="{colors['text']}">Followers: {stats['followers']}</text>
  <text x="20" y="150" fill="{colors['text']}">Commits (last year): {stats['commits']}</text>
  <text x="20" y="280" fill="{colors['text']}" font-size="10px" opacity="0.6">Last updated: {today}</text>
</svg>"""
    return svg


def main():
    stats = get_basic_stats(USERNAME)
    for theme in ("light", "dark"):
        svg = render_svg(stats, theme)
        with open(f"{theme}_mode.svg", "w", encoding="utf-8") as f:
            f.write(svg)
    print("Generated light_mode.svg and dark_mode.svg with stats:", stats)


if __name__ == "__main__":
    main()
