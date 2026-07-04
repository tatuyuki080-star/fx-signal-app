import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /*
   * allowedDevOrigins
   * =================
   * 開発サーバー(next dev)は、知らないホストからのアクセスを
   * デフォルトでブロックする安全機能を持っている。
   * 同じWi-Fi内の他の端末(スマホ・別のPC)からIPアドレス経由で
   * アクセスできるようにするため、許可するホストをここに追加する。
   *
   * 注意: ここに書いたIPアドレスは「自分のMacのWi-Fi上のIPアドレス」。
   *       ネットワークが変わる(別のWi-Fiに繋ぎ直す等)と、
   *       IPアドレスも変わるため、その都度ここを更新する必要がある。
   */
  allowedDevOrigins: ["192.168.0.73"],
};

export default nextConfig;