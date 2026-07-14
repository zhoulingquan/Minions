/**
 * MediaPreview — renders image / video / audio / file preview.
 *
 * Shared by all media-related tool cards (view_image, view_video,
 * desktop_screenshot, send_file_to_user, and the default fallback).
 */

import React, { useCallback, useEffect, useState } from "react";
import { Attachments } from "@agentscope-ai/chat";
import { Audio, Video } from "@agentscope-ai/design";
import { Image, ConfigProvider, Alert } from "antd";
import type { Locale } from "antd/es/locale";
import { DownloadOutlined } from "@ant-design/icons";
import type { MediaInfo } from "./utils";
import { openExternalLink } from "../../../../utils/openExternalLink";
import styles from "./toolCards.module.less";

export interface MediaPreviewProps {
  media: MediaInfo;
}

/** Fetch the preview URL and return the HTTP status code + detail code. */
async function fetchPreviewError(
  url: string,
): Promise<{ status: number; code: string }> {
  try {
    const res = await fetch(url);
    if (res.ok) return { status: 200, code: "" };
    const body = await res.json().catch(() => null);
    return { status: res.status, code: body?.detail ?? "" };
  } catch {
    return { status: 0, code: "NETWORK_ERROR" };
  }
}

const MediaPreview: React.FC<MediaPreviewProps> = ({ media }) => {
    const [error, setError] = useState<string | null>(null);

  const resolveError = useCallback(
    ({ status, code }: { status: number; code: string }) => {
      if (status === 403) {
        setError("访问被拒绝：没有预览此文件的权限。");
      } else if (status === 404) {
        setError("文件未找到，可能已被移动或删除。如果使用了相对路径，请尝试使用绝对路径。");
      } else if (code) {
        setError(`加载文件预览失败：${code}`);
      } else {
        setError("加载文件预览失败。");
      }
    },
    [],
  );

  const handleMediaError = useCallback(() => {
    fetchPreviewError(media.url).then(resolveError);
  }, [media.url, resolveError]);

  // For "file" type there is no native onError — proactively HEAD-check the URL
  useEffect(() => {
    if (media.type !== "file" || !media.url) return;
    let cancelled = false;
    fetchPreviewError(media.url).then((result) => {
      if (!cancelled && result.status !== 200) {
        resolveError(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [media.type, media.url, resolveError]);

  if (error) {
    const description = media.name ? media.name : undefined;
    return (
      <div className={styles.toolCallMediaPreview}>
        <Alert
          type="warning"
          showIcon
          message={error}
          description={description}
        />
      </div>
    );
  }

  return (
    <div className={styles.toolCallMediaPreview}>
      {media.type === "image" && (
        <ConfigProvider locale={{ Image: { preview: "" } } as Locale}>
          <div className={styles.toolCallImage}>
            <Image
              src={media.url}
              style={{ width: "100%", objectFit: "contain" }}
              preview={{ transitionName: "" }}
              onError={handleMediaError}
            />
          </div>
        </ConfigProvider>
      )}
      {media.type === "video" && (
        <div className={styles.bubbleVideo}>
          <Video src={media.url} controls onError={handleMediaError} />
        </div>
      )}
      {media.type === "audio" && (
        <div className={styles.bubbleAudio}>
          <Audio src={media.url} onError={handleMediaError} />
        </div>
      )}
      {media.type === "file" && (
        <div className={styles.bubbleFile}>
          <Attachments.FileCard
            item={{
              uid: media.name,
              name: media.name,
              url: media.url,
              status: "done",
            }}
          />
          {media.url && (
            <div
              className={styles.bubbleFileDownload}
              onClick={() => openExternalLink(media.url)}
            >
              <DownloadOutlined />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MediaPreview;
