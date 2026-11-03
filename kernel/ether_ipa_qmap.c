// SPDX-License-Identifier: GPL-2.0
/* Configure the already-open downstream WAN producer using the driver's
 * QMAP deaggregation settings. No pipe allocation or subsystem restart.
 * Unloading restores the original non-aggregated producer configuration.
 */
#include <linux/module.h>
#include <linux/ipa.h>

static int endpoint;

static int configure(bool deaggregate)
{
    struct ipa_ep_cfg_hdr hdr = {0};
    struct ipa_ep_cfg_hdr_ext ext = {0};
    struct ipa_ep_cfg_aggr aggr = {0};
    struct ipa_ep_cfg_deaggr deaggr = {0};
    int rc;

    hdr.hdr_len = 4;
    hdr.hdr_ofst_metadata_valid = 1;
    if (deaggregate) {
        hdr.hdr_ofst_pkt_size = 2;
        ext.hdr_total_len_or_pad_valid = true;
        ext.hdr_total_len_or_pad = IPA_HDR_PAD;
        ext.hdr_pad_to_alignment = 2;
        ext.hdr_payload_len_inc_padding = true;
        aggr.aggr_en = IPA_ENABLE_DEAGGR;
        aggr.aggr = IPA_QCMAP;
    }
    rc = ipa_cfg_ep_hdr(endpoint, &hdr);
    if (rc) return rc;
    rc = ipa_cfg_ep_hdr_ext(endpoint, &ext);
    if (rc) return rc;
    rc = ipa_cfg_ep_deaggr(endpoint, &deaggr);
    if (rc) return rc;
    return ipa_cfg_ep_aggr(endpoint, &aggr);
}

static int __init qmap_init(void)
{
    int rc;
    endpoint = ipa_get_ep_mapping(IPA_CLIENT_APPS_WAN_PROD);
    if (endpoint != 2) return -ENODEV;
    rc = configure(true);
    if (rc) configure(false);
    pr_info("ether_ipa_qmap: WAN producer QMAP configuration result %d\n", rc);
    return rc;
}

static void __exit qmap_exit(void)
{
    pr_info("ether_ipa_qmap: restore result %d\n", configure(false));
}

module_init(qmap_init);
module_exit(qmap_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Downstream IPA WAN QMAP format diagnostic");
