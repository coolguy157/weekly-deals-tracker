"""
Video Circular Extraction & Processing Pipeline.
Downloads video flyers, extracts high-resolution page keyframes with OpenCV,
and persists structured circular items into the SQLite database with trust tagging.
"""

import urllib.request
import cv2
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from .database import DealsDatabase
from .fetcher import FlyerMetadata
from .normalizer import NormalizedDeal

logger = logging.getLogger(__name__)


class VideoAdPipeline:
    """End-to-end pipeline for processing animated/video weekly ad circulars."""

    def __init__(self, db: Optional[DealsDatabase] = None, data_dir: Optional[str] = None):
        self.db = db or DealsDatabase()
        if data_dir is None:
            base_dir = Path(__file__).resolve().parent.parent / "data"
            self.frames_dir = base_dir / "video_frames"
        else:
            self.frames_dir = Path(data_dir) / "video_frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)

    def download_video(self, video_url: str, dest_path: Optional[str] = None) -> Path:
        """Download video payload from URL to local disk."""
        if dest_path:
            out_path = Path(dest_path)
        else:
            out_path = self.frames_dir / "temp_ad_video.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        req = urllib.request.Request(
            video_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        logger.info(f"Downloading video circular from {video_url[:60]}... to {out_path}")
        with urllib.request.urlopen(req, timeout=45) as resp, open(out_path, "wb") as f:
            f.write(resp.read())

        return out_path

    def extract_page_frames(
        self,
        video_path: str,
        flyer_id: int,
        timestamps: Optional[List[float]] = None,
        num_pages: int = 6,
    ) -> List[Path]:
        """Extract high-resolution static page frames from an ad video."""
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(str(video_file))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        target_dir = self.frames_dir / str(flyer_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Compute sampling timestamps if not explicitly given
        if not timestamps:
            # Spread evenly across the video
            step = duration / (num_pages + 1)
            timestamps = [step * (i + 0.5) for i in range(num_pages)]

        extracted_paths: List[Path] = []
        for page_idx, t in enumerate(timestamps, start=1):
            frame_idx = min(int(t * fps), total_frames - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret:
                frame_path = target_dir / f"page_{page_idx}.png"
                cv2.imwrite(str(frame_path), frame)
                extracted_paths.append(frame_path)
                logger.info(f"Extracted page {page_idx} at {t:.2f}s -> {frame_path}")

        cap.release()
        return extracted_paths

    def ingest_video_deals(
        self,
        flyer_id: int,
        name: str,
        valid_from: str,
        valid_to: str,
        pages_items: List[Dict[str, Any]],
        merchant: str = "Tom Thumb",
        postal_code: str = "00000",
        is_trusted: bool = False,
        source_type: str = "video_ocr_untrusted",
    ) -> int:
        """Persist structured video deals into SQLite with source/trust tagging."""
        meta = FlyerMetadata(
            id=flyer_id,
            merchant=merchant,
            merchant_id=1,
            name=name,
            postal_code=postal_code,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self.db.upsert_flyer_run(meta, is_trusted=is_trusted, source_type=source_type)

        deals_to_insert = []
        deal_counter = 1

        for page in pages_items:
            pg_num = page.get("page_number", 1)
            is_front = page.get("is_front_page", pg_num == 1)

            for item in page.get("items", []):
                price = item.get("price")
                unit_size = item.get("unit_size")
                unit_type = item.get("unit_type")
                unit_price = None
                if price and unit_size and unit_size > 0:
                    unit_price = round(price / unit_size, 4)

                deal = NormalizedDeal(
                    raw_deal_id=flyer_id * 1000 + deal_counter,
                    flyer_id=flyer_id,
                    page_number=pg_num,
                    is_front_page=is_front,
                    canonical_name=item["name"].strip(),
                    brand=item.get("brand"),
                    advertised_price=price,
                    unit_size=unit_size,
                    unit_type=unit_type,
                    unit_price=unit_price,
                    raw_title=item["name"],
                    image_url=item.get("image_url"),
                    promo_type=item.get("promo_type", "member_card" if price else "standard"),
                    is_trusted=is_trusted,
                    source_type=source_type,
                )
                deals_to_insert.append(deal)
                deal_counter += 1

        return self.db.record_deals(deals_to_insert)
