
package com.pointy.lang;

import com.intellij.openapi.fileTypes.LanguageFileType;
import javax.swing.*;
import org.jetbrains.annotations.NotNull;

public class PointyFileType extends LanguageFileType {
    public static final PointyFileType INSTANCE = new PointyFileType();

    private PointyFileType() {
        super(PointyLanguage.INSTANCE);
    }

    @NotNull
    @Override
    public String getName() { return "Pointy file"; }

    @NotNull
    @Override
    public String getDescription() { return "Pointy-lang file"; }

    @NotNull
    @Override
    public String getDefaultExtension() { return "pty"; }

    @Override
    public Icon getIcon() { return null; }
}
