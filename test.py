import httpx
import asyncio


async def get_semgrep_findings(api_token: str, deployment_slug: str, issue_type: str = None):
    """
    Fetch findings (code or supply chain) from Semgrep's MCP Findings API.

    Args:
        api_token (str): Your Semgrep API token.
        deployment_slug (str): The slug of the Semgrep deployment.
        issue_type (str, optional): Optional filter for finding type ('code', 'supply_chain').

    Returns:
        dict: The JSON response from the findings endpoint.
    """
    url = f"https://semgrep.dev/api/v1/deployments/{deployment_slug}/findings"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json"
    }

    params = {}
    if issue_type:
        params['issue_type'] = issue_type

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch findings: {response.status_code} {response.text}")

    return response.json()

# Example usage:
async def main():
    findings = await get_semgrep_findings(api_token="80249dbedff95eed7ac5d4705faab26d6e13aa5f1f80d162a1a290320e7158c4", deployment_slug="flaper87", issue_type="sca")
    print(findings)

asyncio.run(main())

