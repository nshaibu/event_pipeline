
plugins {
    id("org.jetbrains.intellij") version "1.15.0"
    java
}

group = "com.pointy.lang"
version = "0.1.0"

repositories {
    mavenCentral()
}

intellij {
    version.set("2022.3")
}

tasks {
    patchPluginXml {
        changeNotes.set("Initial stub plugin with syntax highlighting for Pointy-lang")
    }
}
