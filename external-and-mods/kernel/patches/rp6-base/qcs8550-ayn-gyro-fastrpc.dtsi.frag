/* ADSP FastRPC remote heap + SensorsPD PDR for AYN SM8550 gyro.
 * Applied to qcs8550-ayn-common.dtsi (odin2 / mini / portal / thor).
 *
 * Do NOT put PD-type on compute-cbs here. PD-type routing is only forced
 * on Thor's stock SH5001 ADSP; Odin 2 uses first-free session banks
 * with SensorsPD attach (INIT_ATTACH_SNS), matching its validated DT.
 */

#include <dt-bindings/firmware/qcom,scm.h>

&{/reserved-memory} {
	adsp_rpc_remote_heap_mem: adsp-rpc-remote-heap {
		compatible = "shared-dma-pool";
		alloc-ranges = <0x0 0x00000000 0x0 0xffffffff>;
		alignment = <0x0 0x400000>;
		size = <0x0 0xc00000>;
		/*
		 * no-map, not reusable: from Linux 7.3.4 / 7.4 fastrpc hands the
		 * whole region to the ADSP at probe. A reusable (CMA) pool keeps
		 * lending those pages to Linux, and the board resets under memory
		 * pressure (issue 102).
		 */
		no-map;
	};
};

&remoteproc_adsp {
	glink-edge {
		fastrpc {
			memory-region = <&adsp_rpc_remote_heap_mem>;
			qcom,fastrpc-adsp-sensors-pdr;
			qcom,vmids = <QCOM_SCM_VMID_LPASS QCOM_SCM_VMID_ADSP_HEAP>;
		};
	};
};
