from httpx import AsyncClient

AD = "Senior Data Engineer\nLumen Payments\nSpark, Kafka and Airflow."


async def test_create_list_get_delete(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/jobs",
        json={"description": AD, "title": " Data engineer ", "url": "https://jobs.example/1"},
    )

    assert created.status_code == 201
    job = created.json()
    assert (job["title"], job["company"], job["url"]) == (
        "Data engineer",
        "",
        "https://jobs.example/1",
    )
    assert job["analysis"] is None
    listed = (await client.get("/api/v1/jobs")).json()
    assert [j["id"] for j in listed] == [job["id"]]
    assert "description" not in listed[0]
    assert (await client.get(f"/api/v1/jobs/{job['id']}")).json()["description"] == AD

    assert (await client.delete(f"/api/v1/jobs/{job['id']}")).status_code == 204
    assert (await client.get(f"/api/v1/jobs/{job['id']}")).status_code == 404


async def test_descriptions_are_required_and_bounded(client: AsyncClient) -> None:
    empty = await client.post("/api/v1/jobs", json={"description": ""})
    huge = await client.post("/api/v1/jobs", json={"description": "x" * 30_001})

    assert (empty.status_code, huge.status_code) == (422, 422)


async def test_jobs_are_private(client: AsyncClient, other_client: AsyncClient) -> None:
    job = (await client.post("/api/v1/jobs", json={"description": AD})).json()

    assert (await other_client.get("/api/v1/jobs")).json() == []
    assert (await other_client.get(f"/api/v1/jobs/{job['id']}")).status_code == 404
    assert (await other_client.delete(f"/api/v1/jobs/{job['id']}")).status_code == 404
