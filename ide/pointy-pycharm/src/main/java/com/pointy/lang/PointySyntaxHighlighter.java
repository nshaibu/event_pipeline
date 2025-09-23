
package com.pointy.lang;

import com.intellij.openapi.editor.DefaultLanguageHighlighterColors;
import com.intellij.openapi.editor.colors.TextAttributesKey;
import com.intellij.openapi.fileTypes.SyntaxHighlighterBase;
import com.intellij.psi.tree.IElementType;
import org.jetbrains.annotations.NotNull;

import static com.intellij.openapi.editor.colors.TextAttributesKey.createTextAttributesKey;

public class PointySyntaxHighlighter extends SyntaxHighlighterBase {
    public static final TextAttributesKey EVENT =
        createTextAttributesKey("POINTY_EVENT", DefaultLanguageHighlighterColors.FUNCTION_DECLARATION);
    public static final TextAttributesKey OPERATOR =
        createTextAttributesKey("POINTY_OPERATOR", DefaultLanguageHighlighterColors.OPERATION_SIGN);
    public static final TextAttributesKey CONDITION =
        createTextAttributesKey("POINTY_CONDITION", DefaultLanguageHighlighterColors.NUMBER);
    public static final TextAttributesKey COMMENT =
        createTextAttributesKey("POINTY_COMMENT", DefaultLanguageHighlighterColors.LINE_COMMENT);

    @NotNull
    @Override
    public com.intellij.lexer.Lexer getHighlightingLexer() {
        return new PointyStubLexer();
    }

    @NotNull
    @Override
    public TextAttributesKey[] getTokenHighlights(IElementType tokenType) {
        if (tokenType.toString().equals("EVENT")) return pack(EVENT);
        if (tokenType.toString().equals("OPERATOR")) return pack(OPERATOR);
        if (tokenType.toString().equals("CONDITION")) return pack(CONDITION);
        if (tokenType.toString().equals("COMMENT")) return pack(COMMENT);
        return TextAttributesKey.EMPTY_ARRAY;
    }
}
