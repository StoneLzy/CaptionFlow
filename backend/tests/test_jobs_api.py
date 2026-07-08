def test_health(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert "checks" in payload
    assert "ffmpeg" in payload["checks"]
    assert "asr" in payload["checks"]


def test_list_jobs_starts_empty(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))

    response = client.get("/api/jobs")

    assert response.status_code == 200
    assert response.json() == []


def test_create_video_job_copies_input(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video",
        data={"config_json": "{}"},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "sample.mp4"
    assert (tmp_path / "jobs" / payload["id"] / "input.mp4").exists()
    upload = next(stage for stage in payload["progress"] if stage["name"] == "upload")
    assert upload["status"] == "completed"
    assert upload["percent"] == 100


def test_create_video_job_uses_custom_job_name(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video",
        data={"config_json": '{"job_name": "My Custom Job"}'},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "My Custom Job"
    assert response.json()["output_directory"] == ""


def test_create_srt_job_copies_source_srt(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/srt",
        data={"config_json": "{}"},
        files={
            "file": (
                "source.srt",
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                "application/x-subrip",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "source.srt"
    assert (tmp_path / "jobs" / payload["id"] / "source.srt").exists()


def test_get_job_returns_detail(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    created = client.post(
        "/api/jobs/srt",
        data={"config_json": "{}"},
        files={
            "file": (
                "source.srt",
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                "application/x-subrip",
            )
        },
    ).json()

    response = client.get(f"/api/jobs/{created['id']}")

    assert response.status_code == 200
    assert response.json()["filename"] == "source.srt"
    assert response.json()["config"]["target_language"] == "zh-Hans"


def test_run_job_queues_background_task(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))
    executed: list[str] = []

    def fake_execute(job_id):
        executed.append(str(job_id))

    monkeypatch.setattr("app.api.jobs.execute_job", fake_execute)

    created = client.post(
        "/api/jobs/srt",
        data={"config_json": "{}"},
        files={
            "file": (
                "source.srt",
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                "application/x-subrip",
            )
        },
    ).json()

    response = client.post(f"/api/jobs/{created['id']}/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "running"
    assert executed == [created["id"]]


def test_open_job_folder_opens_job_directory(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))
    opened: list[str] = []

    monkeypatch.setattr("app.api.jobs.open_folder", lambda path: opened.append(str(path)))

    created = client.post(
        "/api/jobs/video",
        data={"config_json": "{}"},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    ).json()

    response = client.post(f"/api/jobs/{created['id']}/open-folder")

    assert response.status_code == 200
    assert response.json() == {"opened": True}
    assert opened == [str(tmp_path / "jobs" / created["id"])]


def test_open_job_folder_prefers_custom_output_directory(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))
    opened: list[str] = []
    output_dir = tmp_path / "exports"
    output_dir.mkdir()

    monkeypatch.setattr("app.api.jobs.open_folder", lambda path: opened.append(str(path)))

    created = client.post(
        "/api/jobs/video",
        data={"config_json": f'{{"output_directory": "{output_dir}"}}'},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    ).json()

    response = client.post(f"/api/jobs/{created['id']}/open-folder")

    assert response.status_code == 200
    assert response.json() == {"opened": True}
    assert opened == [str(output_dir)]


def test_open_job_folder_returns_404_for_missing_job(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post("/api/jobs/00000000-0000-0000-0000-000000000000/open-folder")

    assert response.status_code == 404


def test_create_video_job_requires_audio_when_track_mux_enabled(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video",
        data={
            "config_json": '{"track_mux_settings": {"enabled": true}}',
        },
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    )

    assert response.status_code == 400
    assert "audio file is required" in response.json()["detail"]


def test_create_video_job_with_track_mux_saves_separate_tracks(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video",
        data={
            "config_json": '{"track_mux_settings": {"enabled": true}}',
        },
        files={
            "file": ("sample.mp4", b"video", "video/mp4"),
            "audio_file": ("external.m4a", b"audio", "audio/mp4"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    job_dir = tmp_path / "jobs" / payload["id"]
    assert (job_dir / "input_video.mp4").exists()
    assert (job_dir / "input_audio.m4a").exists()
    assert not (job_dir / "input.mp4").exists()
    stage_names = [stage["name"] for stage in payload["progress"]]
    assert stage_names == [
        "upload",
        "download",
        "track_mux",
        "transcription",
        "merge",
        "translation",
        "export",
    ]


def test_create_video_from_url_job(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video-from-url",
        data={
            "config_json": (
                '{"media_source":"ytdlp","ytdlp_settings":{"url":"https://example.com/watch?v=abc"}}'
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    job_dir = tmp_path / "jobs" / payload["id"]
    assert (job_dir / "source.url").read_text(encoding="utf-8") == "https://example.com/watch?v=abc"
    upload = next(stage for stage in payload["progress"] if stage["name"] == "upload")
    assert upload["status"] == "skipped"


def test_create_video_from_url_requires_url(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video-from-url",
        data={"config_json": '{"media_source":"ytdlp"}'},
    )

    assert response.status_code == 400
    assert "URL is required" in response.json()["detail"]


def test_translate_job_queues_background_task(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))
    executed: list[str] = []

    def fake_execute(job_id):
        executed.append(str(job_id))

    monkeypatch.setattr("app.api.jobs.execute_translate_job", fake_execute)

    created = client.post(
        "/api/jobs/srt",
        data={"config_json": "{}"},
        files={
            "file": (
                "source.srt",
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                "application/x-subrip",
            )
        },
    ).json()
    job_dir = tmp_path / "jobs" / created["id"]
    (job_dir / "transcript.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
        encoding="utf-8",
    )

    response = client.post(f"/api/jobs/{created['id']}/translate")

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert executed == [created["id"]]


def test_create_job_strips_api_key_from_config(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    created = client.post(
        "/api/jobs/srt",
        data={"config_json": '{"provider_settings":{"api_key":"secret-key"}}'},
        files={
            "file": (
                "source.srt",
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                "application/x-subrip",
            )
        },
    ).json()

    response = client.get(f"/api/jobs/{created['id']}")
    assert response.status_code == 200
    assert response.json()["config"]["provider_settings"]["api_key"] == ""


def test_create_video_job_rejects_invalid_extension(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video",
        data={"config_json": "{}"},
        files={"file": ("sample.exe", b"video", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "extensions" in response.json()["detail"]


def test_create_job_rejects_invalid_config_json(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    response = client.post(
        "/api/jobs/video",
        data={"config_json": "not-json"},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    )

    assert response.status_code == 400
    assert "Invalid config_json" in response.json()["detail"]


def test_delete_job_removes_record_and_files(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    created = client.post(
        "/api/jobs/video",
        data={"config_json": "{}"},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    ).json()
    job_dir = tmp_path / "jobs" / created["id"]
    assert job_dir.exists()

    response = client.delete(f"/api/jobs/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/jobs/{created['id']}").status_code == 404
    assert not job_dir.exists()


def test_cancel_running_job(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    created = client.post(
        "/api/jobs/video",
        data={"config_json": "{}"},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    ).json()
    monkeypatch.setattr("app.api.jobs.execute_job", lambda job_id: None)
    client.post(f"/api/jobs/{created['id']}/run")

    response = client.post(f"/api/jobs/{created['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_download_job_output(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    created = client.post(
        "/api/jobs/srt",
        data={"config_json": "{}"},
        files={
            "file": (
                "source.srt",
                b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
                "application/x-subrip",
            )
        },
    ).json()
    job_dir = tmp_path / "jobs" / created["id"]
    transcript = job_dir / "transcript.srt"
    transcript.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    from app.jobs.repository import JobRepository

    repo = JobRepository(tmp_path / "app.db")
    from uuid import UUID

    repo.set_outputs(UUID(created["id"]), {"transcript_srt": str(transcript)})

    response = client.get(f"/api/jobs/{created['id']}/outputs/transcript_srt/download")

    assert response.status_code == 200
    assert "Hello" in response.text


def test_rename_job_updates_filename(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    created = client.post(
        "/api/jobs/video",
        data={"config_json": "{}"},
        files={"file": ("sample.mp4", b"video", "video/mp4")},
    ).json()

    response = client.patch(
        f"/api/jobs/{created['id']}",
        json={"filename": "My renamed task"},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "My renamed task"
    assert client.get(f"/api/jobs/{created['id']}").json()["filename"] == "My renamed task"
