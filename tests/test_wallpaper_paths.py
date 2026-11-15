from src import shell_config
from src.pages import wallpaper


def test_video_dir_uses_wallpaper_dir(monkeypatch, tmp_path):
    root = tmp_path / "Wallpapers"
    monkeypatch.setattr(shell_config, "wallpaper_dir", lambda: root)
    assert wallpaper.video_dir() == root / "Animated"


def test_scan_separates_images_and_animated_videos(monkeypatch, tmp_path):
    root = tmp_path / "Wallpapers"
    animated = root / "Animated"
    animated.mkdir(parents=True)
    (root / "still.png").write_bytes(b"x")
    (root / "nested").mkdir()
    (root / "nested" / "more.jpg").write_bytes(b"x")
    (animated / "preview.png").write_bytes(b"x")
    (animated / "loop.mp4").write_bytes(b"x")

    monkeypatch.setattr(shell_config, "wallpaper_dir", lambda: root)

    images = wallpaper._scan(
        root, wallpaper.IMAGE_EXTENSIONS, exclude=wallpaper.video_dir()
    )
    assert [path.name for path in images] == ["more.jpg", "still.png"]

    videos = wallpaper._scan(wallpaper.video_dir(), wallpaper.VIDEO_EXTENSIONS)
    assert [path.name for path in videos] == ["loop.mp4"]
