1. Open it in **IntelliJ IDEA** (Community is fine).
2. Run:
   ```bash
   ./gradlew buildPlugin
   ```

   This will produce:
   ```
   build/distributions/pointy-lang-0.1.0.zip
   ```

   That `.zip` **is the actual installable PyCharm plugin**.
3. In **PyCharm**, go to
   `Settings → Plugins → ⚙ → Install Plugin from Disk...`
   and select that zip.
