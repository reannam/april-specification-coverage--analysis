import { Fragment } from "react";
import { escapeRegExp } from "../../utils/formatters";

export default function HighlightedText({
  text,
  terms = [],
}: {
  text: string;
  terms?: string[];
}) {
  const uniqueTerms = [...new Set(terms.map((term) => term.trim()).filter(Boolean))]
    .sort((first, second) => second.length - first.length);

  if (!uniqueTerms.length) {
    return <>{text}</>;
  }

  const expression = new RegExp(
    `(${uniqueTerms.map(escapeRegExp).join("|")})`,
    "gi",
  );

  return (
    <>
      {text.split(expression).map((part, index) => {
        const matched = uniqueTerms.some(
          (term) => term.toLowerCase() === part.toLowerCase(),
        );

        return matched ? (
          <mark key={`${part}-${index}`}>{part}</mark>
        ) : (
          <Fragment key={`${part}-${index}`}>{part}</Fragment>
        );
      })}
    </>
  );
}
