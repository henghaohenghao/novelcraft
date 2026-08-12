"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Collaboration from "@tiptap/extension-collaboration";
import CollaborationCursor from "@tiptap/extension-collaboration-cursor";
import type * as Y from "yjs";
import type { Awareness } from "y-protocols/awareness";

interface CollaborationEditorInnerProps {
  ydoc: Y.Doc;
  awareness: Awareness;
  userName: string;
  userColor: string;
}

export default function CollaborationEditorInner({
  ydoc,
  awareness,
  userName,
  userColor,
}: CollaborationEditorInnerProps) {
  console.log("CollaborationEditorInner - awareness:", awareness);

  // 创建一个包装对象，因为 CollaborationCursor 期望 provider 有 awareness 属性
  const provider = awareness ? { awareness } : null;

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        history: false,
      }),
      Collaboration.configure({
        document: ydoc,
      }),
      ...(provider
        ? [
            CollaborationCursor.configure({
              provider: provider as any,
              user: {
                name: userName,
                color: userColor,
              },
            }),
          ]
        : []),
    ],
    content: "",
  });

  if (!editor) return null;

  return (
    <div className="relative">
      <EditorContent
        editor={editor}
        className="prose prose-lg max-w-none min-h-[500px] focus:outline-none border border-claude-border rounded-lg p-4 bg-white"
      />

      <style jsx global>{`
        /* 光标样式 */
        .collaboration-cursor__caret {
          position: relative;
          margin-left: -1px;
          margin-right: -1px;
          border-left: 1px solid #0d0d0d;
          border-right: 1px solid #0d0d0d;
          word-break: normal;
          pointer-events: none;
        }

        .collaboration-cursor__label {
          position: absolute;
          top: -1.4em;
          left: -1px;
          font-size: 12px;
          font-style: normal;
          font-weight: 600;
          line-height: normal;
          user-select: none;
          color: #fff;
          padding: 0.1rem 0.3rem;
          border-radius: 3px 3px 3px 0;
          white-space: nowrap;
        }

        /* 选区样式 */
        .collaboration-cursor__selection {
          opacity: 0.3;
        }
      `}</style>
    </div>
  );
}
