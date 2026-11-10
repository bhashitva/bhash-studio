// SPDX-License-Identifier: Apache-2.0
import java.nio.charset.StandardCharsets;
import java.util.Base64;

/** Preserve Hindi arguments across Windows launchers using legacy code pages. */
class BhashStudioLauncher {
    public static void main(String[] args) throws Exception {
        String[] decoded = new String[args.length];
        for (int index = 0; index < args.length; index++) {
            decoded[index] = new String(Base64.getUrlDecoder().decode(args[index]), StandardCharsets.UTF_8);
        }
        dev.bhash.cli.Main.main(decoded);
    }
}
