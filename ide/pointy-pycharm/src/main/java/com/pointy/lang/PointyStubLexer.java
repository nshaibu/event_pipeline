
package com.pointy.lang;

import com.intellij.lexer.LexerBase;
import com.intellij.psi.tree.IElementType;
import com.intellij.psi.TokenType;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

public class PointyStubLexer extends LexerBase {
    private CharSequence buffer;
    private int startOffset;
    private int endOffset;
    private int state;
    private IElementType tokenType;

    @Override
    public void start(@NotNull CharSequence buffer, int startOffset, int endOffset, int initialState) {
        this.buffer = buffer;
        this.startOffset = startOffset;
        this.endOffset = startOffset;
        this.state = initialState;
        advance();
    }

    @Override
    public int getState() { return state; }

    @Nullable
    @Override
    public IElementType getTokenType() { return tokenType; }

    @Override
    public int getTokenStart() { return startOffset; }

    @Override
    public int getTokenEnd() { return endOffset; }

    @Override
    public void advance() {
        if (endOffset >= buffer.length()) {
            tokenType = null;
            return;
        }
        char c = buffer.charAt(endOffset);
        startOffset = endOffset;
        if (c == '#') {
            while (endOffset < buffer.length() && buffer.charAt(endOffset) != '\n') endOffset++;
            tokenType = new IElementType("COMMENT", PointyLanguage.INSTANCE);
            return;
        }
        if (Character.isUpperCase(c)) {
            while (endOffset < buffer.length() && Character.isJavaIdentifierPart(buffer.charAt(endOffset))) endOffset++;
            tokenType = new IElementType("EVENT", PointyLanguage.INSTANCE);
            return;
        }
        if (c == '-' || c == '|' || c == '*' || c == 'X') {
            while (endOffset < buffer.length() && "!->|X*".indexOf(buffer.charAt(endOffset)) >= 0) endOffset++;
            tokenType = new IElementType("OPERATOR", PointyLanguage.INSTANCE);
            return;
        }
        if (c == '0' || c == '1') {
            endOffset++;
            tokenType = new IElementType("CONDITION", PointyLanguage.INSTANCE);
            return;
        }
        endOffset++;
        tokenType = TokenType.BAD_CHARACTER;
    }

    @NotNull
    @Override
    public CharSequence getBufferSequence() { return buffer; }

    @Override
    public int getBufferEnd() { return buffer.length(); }
}
