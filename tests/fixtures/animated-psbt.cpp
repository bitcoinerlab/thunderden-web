// Public BIP39 fixture producer. Host-side development tool, never guest code.
#include "keys.h"
#include "policy.h"
#include "transport.h"
#include <chainparams.h>
#include <crypto/sha256.h>
#include <psbt.h>
#include <streams.h>
#include <univalue.h>
#include <util/strencodings.h>
#include <iostream>

int main()
{
    ECC_Context context;
    SelectParams(ChainType::MAIN);
    const std::string words = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about";
    td::Keys keys({reinterpret_cast<const uint8_t*>(words.data()), words.size()}, {});
    const td::Path account{0x80000054, 0x80000000, 0x80000000};
    const auto origin = "[" + HexStr(keys.RootFingerprint()) + "/84h/0h/0h]";
    td::Policy policy("Public fixture", "wpkh(@0/**)", {origin + td::EncodePublic(keys.PublicAt(account), true)}, true);
    CMutableTransaction tx;
    std::vector<CTransactionRef> previous;
    for (unsigned i = 0; i < 5; ++i) {
        CMutableTransaction funding;
        uint256 id; id.begin()[0] = i + 1;
        funding.vin.emplace_back(COutPoint(Txid::FromUint256(id), 0));
        funding.vout.emplace_back(100000, policy.Script(0, i));
        previous.push_back(MakeTransactionRef(funding));
        tx.vin.emplace_back(COutPoint(previous.back()->GetHash(), 0), CScript{}, 0xfffffffd);
    }
    tx.vout.emplace_back(200000, CScript{} << OP_0 << std::vector<uint8_t>(20, 0x42));
    tx.vout.emplace_back(299000, policy.Script(1, 0));
    PartiallySignedTransaction psbt(tx);
    for (unsigned i = 0; i < previous.size(); ++i) {
        psbt.inputs[i].non_witness_utxo = previous[i];
        const auto data = PrecomputePSBTData(psbt);
        const auto status = SignPSBTInput(policy.PublicProvider({0, i}), psbt, i, &data, std::nullopt, nullptr, false);
        td::Require(status == PSBTError::OK || status == PSBTError::INCOMPLETE, "Fixture metadata failed");
    }
    UpdatePSBTOutput(policy.PublicProvider({1, 0}), psbt, 1);
    DataStream stream; stream << psbt;
    const auto bytes = std::span(reinterpret_cast<const uint8_t*>(stream.data()), stream.size());
    td::Digest digest;
    CSHA256().Write(bytes.data(), bytes.size()).Finalize(digest.data());
    td::URSender sender({"crypto-psbt", td::CborBytes(bytes)}, 200);
    UniValue result(UniValue::VOBJ), frames(UniValue::VARR);
    result.pushKV("bytes", stream.size()); result.pushKV("parts", sender.Parts());
    result.pushKV("psbt_sha256", HexStr(digest));
    result.pushKV("payment_sats", 200000); result.pushKV("change_sats", 299000); result.pushKV("fee_sats", 1000);
    for (size_t i = 0; i < sender.Parts() * 2; ++i) frames.push_back(sender.Next());
    result.pushKV("frames", frames);
    std::cout << result.write() << '\n';
}
