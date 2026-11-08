#!/usr/bin/env python3
"""Archive-only PE ARM GCC 4.9 and pinned mondrian compat-vDSO source checks.

Never run or download obsolete GCC executables; this is not kernel build CI.
External source files must be fetched from the exact commits in the audit doc.
"""
import os
from pathlib import Path
import re
import subprocess
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_COMMIT = "111258a10e017f067b27e6cfcea7619d753f3309"
ARCHIVE_TREE = "e21ca99fc9d742dd0e44b1713360c60bee35d434"
BIN_TREE = "67e5812ebecab0684b5b01bd257ea0445d832b6e"
ARM_PATH = "prebuilts/gcc/linux-x86/arm/arm-linux-androideabi-4.9"
ARM_REPO = "prebuilts_gcc_linux-x86_arm_arm-linux-androideabi-4.9"
HOST_CLANG = "platform/prebuilts/clang/host/linux-x86"
PLATFORM_VERSION = "clang-r584948"

def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()

def entry(tree, path):
    data = git("ls-tree", tree, "--", path)
    if not data:
        raise AssertionError("missing original Git object: " + path)
    details, found = data.split("\t", 1)
    if found != path:
        raise AssertionError("incorrect object: " + data)
    mode, kind, sha = details.split()
    return mode, kind, sha

def external(name):
    path = os.environ.get(name)
    if not path or not Path(path).is_file():
        raise AssertionError("required pinned source input: " + name)
    return Path(path).read_text(encoding="utf-8")

class ArmGcc49ArchiveAudit(unittest.TestCase):
    def test_original_archive_is_an_ancestor_with_exact_tree(self):
        result = subprocess.run(["git", "-C", str(ROOT), "merge-base",
                                 "--is-ancestor", ARCHIVE_COMMIT, "HEAD"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git("rev-parse", ARCHIVE_COMMIT + "^{tree}"), ARCHIVE_TREE)

    def test_original_compilers_and_libs_are_unchanged(self):
        self.assertEqual(entry("HEAD", "bin"), ("040000", "tree", BIN_TREE))
        self.assertEqual(entry("HEAD", "repo.prop"),
                         ("100644", "blob", "a12a59bc5d9a0460e578c9fedbbec58b42e378cc"))
        for directory in ("arm-linux-androideabi", "lib", "libexec"):
            self.assertEqual(entry("HEAD", directory), entry(ARCHIVE_COMMIT, directory))

    def test_legacy_gcc_and_binutils_binary_object_modes(self):
        fixtures = {
            "bin/arm-linux-androideabi-gcc": ("100755", "54944a2ccbea692fa58d912e74b2514dab7a80f5"),
            "bin/real-arm-linux-androideabi-gcc": ("100755", "0bfbd6532e63fd8f984abaa2f360c862b997ccb1"),
            "bin/arm-linux-androideabi-gcc-4.9": ("120000", "b8b9fadd21defcc53903afc7d4c3132efb18077f"),
            "bin/arm-linux-androideabi-as": ("100755", "5194147f6d451a3000040419a07bad05e6f4b235"),
            "bin/arm-linux-androideabi-ld.bfd": ("100755", "3b8686af1f21faabf4cc7c537d2eafd5f9cae543"),
            "bin/arm-linux-androideabi-objcopy": ("100755", "610cf857cf73c39959f4da5df4621009b35e1f4f"),
            "bin/arm-linux-androidkernel-as": ("120000", "0d3f7021f464d13cba89fd4fb498a054b40f4f72"),
        }
        for name, expected in fixtures.items():
            with self.subTest(path=name):
                mode, kind, sha = entry("HEAD", name)
                self.assertEqual(kind, "blob")
                self.assertEqual((mode, sha), expected)

    def test_archive_provenance_and_legacy_wrapper(self):
        source = (ROOT / "repo.prop").read_text(encoding="utf-8")
        self.assertIn("toolchain/gcc ", source)
        self.assertIn("toolchain/binutils ", source)
        self.assertNotIn("android-17.0.0", source)
        self.assertFalse((ROOT / "Android.bp").exists())
        # Wrapper and original GCC binary remain Git objects only.
        self.assertEqual(entry("HEAD", "bin/arm-linux-androideabi-gcc")[2],
                         "54944a2ccbea692fa58d912e74b2514dab7a80f5")

    def test_aosp17_uses_official_platform_clang_not_old_arm_gcc(self):
        tree = ET.fromstring(external("PE_AOSP17_REFERENCE"))
        self.assertEqual(tree.find("default").get("revision"), "refs/tags/android-17.0.0_r1")
        projects = list(tree.iter("project"))
        own = [x for x in projects if x.get("path") == "prebuilts/clang/host/linux-x86"]
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0].get("name"), HOST_CLANG)
        self.assertFalse(any(x.get("path") == ARM_PATH or x.get("name") == ARM_REPO
                             for x in projects))
        soong = external("PE_AOSP17_SOONG_GLOBAL")
        self.assertEqual(re.findall(
            r'(?m)^\s*ClangDefaultVersion\s*=\s*"([^"]+)"', soong), [PLATFORM_VERSION])
        self.assertIn("ReleaseBuildClangVersion(ClangDefaultVersion)", soong)

    def test_active_entrypoint_not_changed_by_archive(self):
        default = ET.fromstring(external("PE_AOSP17_DEFAULT"))
        includes = default.findall("include")
        self.assertEqual([x.get("name") for x in includes],
                         ["aosp17_pe_p2_kernel_configs.xml"])
        self.assertFalse(any(x.get("path") == ARM_PATH or x.get("name") == ARM_REPO
                             for x in default.iter("project")))

    def test_actual_mondrian_kernel_has_distinct_32bit_vdso_path(self):
        vdso = external("PE_KERNEL_VDSO32")
        kconfig = external("PE_KERNEL_ARM64_KCONFIG")
        gki = external("PE_KERNEL_GKI_DEFCONFIG")
        board = external("PE_MONDRIAN_BOARD_CONFIG")
        self.assertIn("CC_COMPAT += --target=arm-linux-gnueabi", vdso)
        self.assertIn("CC_COMPAT ?= $(CROSS_COMPILE_COMPAT)gcc", vdso)
        self.assertIn("LD_COMPAT ?= $(LD)", vdso)
        self.assertIn("LD_COMPAT ?= $(CROSS_COMPILE_COMPAT)ld", vdso)
        self.assertIn("config COMPAT_VDSO", kconfig)
        self.assertIn('depends on (CC_IS_CLANG && LD_IS_LLD) || "$(CROSS_COMPILE_COMPAT)" != ""', kconfig)
        self.assertRegex(gki, r"(?m)^CONFIG_COMPAT=y$")
        self.assertIn("gki_defconfig", board)
        self.assertIn("vendor/$(PRODUCT_DEVICE)_GKI.config", board)
        # CONFIG_COMPAT=y does NOT by itself prove the final COMPAT_VDSO=y:
        # its Kconfig dependency also depends on real compiler/linker choices.

    def test_android_arm_prefix_is_not_gnu_eabi_prefix(self):
        vdso = external("PE_KERNEL_VDSO32")
        self.assertIn("arm-linux-gnueabi", vdso)
        self.assertNotEqual("arm-linux-androideabi-", "arm-linux-gnueabi-")
        # The archived repo has no registered arm-linux-gnueabi- prefix.
        # Do not treat it as a drop-in replacement for GCC/LD_COMPAT.

if __name__ == "__main__":
    unittest.main(verbosity=2)
