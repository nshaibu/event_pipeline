
package com.pointy.lang;

import com.intellij.lang.Language;

public class PointyLanguage extends Language {
    public static final PointyLanguage INSTANCE = new PointyLanguage();
    private PointyLanguage() {
        super("Pointy");
    }
}
