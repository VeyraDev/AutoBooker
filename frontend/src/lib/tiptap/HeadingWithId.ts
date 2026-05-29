import Heading from "@tiptap/extension-heading";

/** Section anchors for outline TOC jump (sec-{chapter}-{section}). */
export const HeadingWithId = Heading.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      id: {
        default: null,
        parseHTML: (element) => element.getAttribute("id"),
        renderHTML: (attributes) => {
          if (!attributes.id) return {};
          return { id: attributes.id };
        },
      },
    };
  },
});
