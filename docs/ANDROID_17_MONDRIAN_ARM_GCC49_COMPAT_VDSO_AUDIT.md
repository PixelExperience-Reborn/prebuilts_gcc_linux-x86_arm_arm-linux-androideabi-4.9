# Stage 190: ARM GCC 4.9 archive and mondrian 32-bit compat-vDSO

**Date:** 2026-11-08. **Target:** POCO F5 Pro / Redmi K60 (mondrian, SM8475). **Base:** independent Google AOSP 17 android-17.0.0_r1. No LineageOS/CLO product imports.

## Archive audit and decision

- Historical PixelExperience repository: https://github.com/PixelExperience-Reborn/prebuilts_gcc_linux-x86_arm_arm-linux-androideabi-4.9
- Original seventeen HEAD: 111258a10e017f067b27e6cfcea7619d753f3309 (2020-09-14); Git tree e21ca99fc9d742dd0e44b1713360c60bee35d434; binary subdirectory Git tree 67e5812ebecab0684b5b01bd257ea0445d832b6e.
- The final archived commit restored GCC4.9 executable names after earlier experiments moved/removed executables to find old build dependencies. This proves historical maintenance, **not modern Android17 requirement**.
- Archive includes compiler wrapper, ARM32 GCC4.9, GNU as, ld.bfd/gold, objcopy, and arm-linux-androidkernel symlinks. Original ELF objects and executable/symlink modes remain unchanged. No old GCC is executed.
- repo.prop lists old toolchain/gcc, toolchain/binutils and GNU libraries, with no Android17 provenance. PE manifest/seventeen listed this repository under snippets/pixel-extras.xml.
- Official Android17 reference does not include this ARM32 GCC49 archive. The official AOSP17 host Clang is prebuilts/clang/host/linux-x86; pinned PE-Reborn build_soong (6215d41c790a463b7795ce81ac77204c238cbf48) has ClangDefaultVersion clang-r584948 for PLATFORM builds only.
- **Decision:** preserve original PE history and Git objects, exclude GCC4.9 as an active AOSP17 source project, and test kernel toolchain independently. This is not an automatic switch to the newest Clang for Linux 5.10.

## Actual SM8475 kernel evidence (read-only reference)

- Kernel reference: LF52406/android_kernel_xiaomi_sm8450 lineage-24.0, SHA 283772ceb84491fd446e340fd211d45fb9dd9a36.
- Device common: LF52406/mondrian_android_device_xiaomi_sm8450-common, SHA 6e0022f5100e09ac97980095b6ed8528f4ff823f.
- In arch/arm64/kernel/vdso32/Makefile, the Clang path sets CC_COMPAT += --target=arm-linux-gnueabi when CONFIG_CC_IS_CLANG=y. GCC fallback uses CC_COMPAT ?= $(CROSS_COMPILE_COMPAT)gcc. LLD uses LD_COMPAT ?= $(LD); GNU fallback uses LD_COMPAT ?= $(CROSS_COMPILE_COMPAT)ld.
- arch/arm64/Kconfig declares COMPAT_VDSO and requires Clang+LLD or a nonempty CROSS_COMPILE_COMPAT. gki_defconfig contains CONFIG_COMPAT=y, but the final CONFIG_COMPAT_VDSO still depends on actual toolchain and merged configuration. These conditions must not be silently disabled to avoid GCC.
- BoardConfigCommon.mk selects gki_defconfig plus vendor/waipio_GKI.config, vendor/xiaomi_GKI.config, vendor/$(PRODUCT_DEVICE)_GKI.config and vendor/debugfs.config. This is existing device-tree reference, NOT a PE-Reborn build result.
- Historical ARM GCC prefix arm-linux-androideabi- differs from the Clang target triple arm-linux-gnueabi. Do not confuse these ABI/triple names or hardwire the old GCC49 as CROSS_COMPILE_COMPAT.
- Official kernel LLVM build guide: https://docs.kernel.org/kbuild/llvm.html

## Implemented and tested here

New host-only unit tests check unchanged historical Git ancestry, tree/blob IDs and executable modes, official AOSP17 manifest/Soong source ownership and exact pinned SM8475 vdso32/Kconfig/GKI/BoardConfig source contracts. CI uses blob-filtered sparse checkout and downloads only specific pinned textual reference files. The companion manifest Draft PR blocks historical ARM GCC4.9 paths/repository aliases in active and candidate graphs, runs two negative import tests and updates row 190 in the 135-repository matrix. Neither historical seventeen nor AOSP17 default.xml is replaced.

## Remaining hard gates

Validate the final PE-Reborn kernel .config, CONFIG_COMPAT/COMPAT_VDSO/THUMB2_COMPAT_VDSO, toolchain versions, CC_COMPAT/LD_COMPAT, LLVM_IAS and LLD. Compile the AArch32 vDSO (ELFCLASS32/EM_ARM, symbols and relocations), Image, DTBs/DTBO and ALL external vendor modules with a single reproducible pinned toolchain. Check Android17 GKI/KMI, module vermagic/ABI, FCM/VINTF/AVB/boot/recovery and real 32-bit application behavior on a physical mondrian.

**Not performed:** a full AOSP17 repo sync, Soong build, actual kernel or vDSO compilation, module ABI, boot or physical device test. CI green is not build compatibility.
