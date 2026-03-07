import re


class LatexResumeParser:

    def extract_text(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            text: str = f.read()
        return self._transform(text)

    def _transform(self, text: str) -> str:
        # 0. Extract only document body (skip preamble)
        body_match: re.Match[str] | None = re.search(
            r'\\begin\{document\}(.*)', text, re.DOTALL
        )
        if body_match:
            text = body_match.group(1)

        # 1. Strip comments (% to end of line, but not escaped \%)
        text = re.sub(r'(?<!\\)%[^\n]*', '', text)

        # 2. LaTeX line break \\ → newline
        text = re.sub(r'\\\\', '\n', text)

        # 3. \section{X} → \nX\n
        text = re.sub(r'\\section\{([^}]*)\}', r'\n\1\n', text)

        # 4. \resumeSubheading{A}{B}{C}{D} → A B\nC D
        text = re.sub(
            r'\\resumeSubheading\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}',
            r'\1 \2\n\3 \4',
            text,
        )

        # 5. Font/inline formatting — 3 passes handles up to 3 nesting levels.
        #    Applied before \resumeProjectHeading and \resumeItem so their args
        #    are clean for the simpler [^}]* pattern.
        for _ in range(3):
            # two-arg \textbf{X}{Y} → XY  (used in Technical Skills section)
            text = re.sub(r'\\textbf\{([^}]*)\}\{([^}]*)\}', r'\1\2', text)
            # single-arg font commands → keep content
            for cmd in ('textbf', 'textit', 'emph', 'small', 'underline'):
                text = re.sub(rf'\\{cmd}\{{([^}}]*)\}}', r'\1', text)
            # \href{url}{text} → text
            text = re.sub(r'\\href\{[^}]*\}\{([^}]*)\}', r'\1', text)

        # 6. \resumeProjectHeading{A}{B} → A B  (args now clean after step 5)
        text = re.sub(
            r'\\resumeProjectHeading\s*\{([^}]*)\}\s*\{([^}]*)\}',
            r'\1 \2',
            text,
        )

        # 7. \resumeItem{X} → • X  (args now clean after step 5)
        text = re.sub(r'\\resumeItem\{([^}]*)\}', '• \\1', text)

        # 8. Escape sequences
        text = text.replace(r'\&', '&')
        text = text.replace(r'\#', '#')
        text = text.replace(r'\$', '$')
        text = text.replace(r'\%', '%')

        # 9. Remove \begin{...} and \end{...} environment markers entirely
        text = re.sub(r'\\(?:begin|end)\{[^}]*\}', '', text)

        # 10. Strip optional [...] arguments
        text = re.sub(r'\[[^\]]*\]', '', text)

        # 11. Remove remaining \command names only (keep what follows — braces
        #     are removed next, so content is preserved without the command name)
        text = re.sub(r'\\[a-zA-Z@]+\*?', '', text)

        # 12. Remove bare { and }
        text = text.replace('{', '').replace('}', '')

        # 13. Normalize whitespace: collapse 3+ newlines to 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text
