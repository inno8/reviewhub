import { diffChars, diffLines } from 'diff';
function chunkLines(value) {
    if (!value)
        return [];
    const norm = value.replace(/\r\n/g, '\n');
    const lines = norm.split('\n');
    if (lines.length && lines[lines.length - 1] === '') {
        lines.pop();
    }
    return lines;
}
function segs(text, kind) {
    return [{ text, kind }];
}
function segmentsFromChars(oldLine, newLine) {
    const parts = diffChars(oldLine, newLine);
    const left = [];
    const right = [];
    for (const p of parts) {
        if (p.added) {
            right.push({ text: p.value, kind: 'add' });
        }
        else if (p.removed) {
            left.push({ text: p.value, kind: 'del' });
        }
        else {
            left.push({ text: p.value, kind: 'neutral' });
            right.push({ text: p.value, kind: 'neutral' });
        }
    }
    return { left, right };
}
/**
 * Split-view diff: aligned rows, optional inline char highlights for paired replace lines.
 */
export function buildSideBySideDiff(oldStr, newStr) {
    const lineParts = diffLines(oldStr || '', newStr || '', { ignoreWhitespace: false });
    let leftLine = 0;
    let rightLine = 0;
    const rows = [];
    let removalRows = 0;
    let additionRows = 0;
    let i = 0;
    while (i < lineParts.length) {
        const cur = lineParts[i];
        const next = lineParts[i + 1];
        if (cur.removed && next?.added) {
            const removedLines = chunkLines(cur.value);
            const addedLines = chunkLines(next.value);
            const max = Math.max(removedLines.length, addedLines.length);
            for (let k = 0; k < max; k++) {
                const L = removedLines[k];
                const R = addedLines[k];
                const hasL = L !== undefined;
                const hasR = R !== undefined;
                if (hasL)
                    leftLine++;
                if (hasR)
                    rightLine++;
                if (hasL && hasR) {
                    const { left, right } = segmentsFromChars(L, R);
                    rows.push({
                        leftNum: leftLine,
                        rightNum: rightLine,
                        leftSegments: left.length ? left : segs(L, 'neutral'),
                        rightSegments: right.length ? right : segs(R, 'neutral'),
                        leftTint: 'removed',
                        rightTint: 'added',
                    });
                    removalRows++;
                    additionRows++;
                }
                else if (hasL) {
                    rows.push({
                        leftNum: leftLine,
                        rightNum: null,
                        leftSegments: segs(L, 'del'),
                        rightSegments: segs('', 'neutral'),
                        leftTint: 'removed',
                        rightTint: 'none',
                    });
                    removalRows++;
                }
                else if (hasR) {
                    rows.push({
                        leftNum: null,
                        rightNum: rightLine,
                        leftSegments: segs('', 'neutral'),
                        rightSegments: segs(R, 'add'),
                        leftTint: 'none',
                        rightTint: 'added',
                    });
                    additionRows++;
                }
            }
            i += 2;
            continue;
        }
        if (cur.added) {
            for (const line of chunkLines(cur.value)) {
                rightLine++;
                additionRows++;
                rows.push({
                    leftNum: null,
                    rightNum: rightLine,
                    leftSegments: segs('', 'neutral'),
                    rightSegments: segs(line, 'add'),
                    leftTint: 'none',
                    rightTint: 'added',
                });
            }
            i++;
            continue;
        }
        if (cur.removed) {
            for (const line of chunkLines(cur.value)) {
                leftLine++;
                removalRows++;
                rows.push({
                    leftNum: leftLine,
                    rightNum: null,
                    leftSegments: segs(line, 'del'),
                    rightSegments: segs('', 'neutral'),
                    leftTint: 'removed',
                    rightTint: 'none',
                });
            }
            i++;
            continue;
        }
        for (const line of chunkLines(cur.value)) {
            leftLine++;
            rightLine++;
            rows.push({
                leftNum: leftLine,
                rightNum: rightLine,
                leftSegments: segs(line, 'neutral'),
                rightSegments: segs(line, 'neutral'),
                leftTint: 'none',
                rightTint: 'none',
            });
        }
        i++;
    }
    return { rows, removalRows, additionRows };
}
