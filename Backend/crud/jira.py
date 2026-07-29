import httpx

async def fetch_jira_user_issues(api_key: str, domain: str, max_results: int = 30) -> list:
    url = f"https://{domain.replace('https://','')}/rest/api/3/search"
    headers = {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json"
    }
    params = {
        "jql": "assignee=currentUser() ORDER BY updated DESC",
        "maxResults": max_results
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"Jira API failed: {response.status_code} {response.text}")

    data = response.json()
    return data.get("issues", [])
