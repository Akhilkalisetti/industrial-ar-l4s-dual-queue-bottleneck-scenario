/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Four-application industrial AR traffic over a DualPI2 bottleneck.
 * This ns-3 checkout does not include TCP Prague.  TcpDctcp is selected as
 * its available ECT(1)-capable L4S congestion-control implementation.
 */

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/csma-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/traffic-control-module.h"
#include "ns3/tcp-socket-base.h"
#include "ns3/ipv4-flow-classifier.h"
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <map>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE ("IndustrialArDualq");

static std::array<Ptr<OnOffApplication>, 4> g_sources;
static bool g_cwndTracesConnected = false;
static std::ofstream g_cwndFile;
static std::ofstream g_queueFile;
static std::ofstream g_sojournFile;
static Ptr<DualQCoupledPi2QueueDisc> g_queueDisc;
static std::string g_experiment;

static const std::array<std::string, 4> g_names = {"video", "instructions", "sensors", "logs"};
static const std::array<double, 4> g_offeredMbps = {{8.0, 4.0, 0.04096, 3.0}};

static double
MeanUtility (uint32_t app, const std::string& experiment, double duration)
{
  if (experiment == "E1")
    {
      return 1.0;
    }
  if (experiment == "E2")
    {
      const std::array<double, 4> fixed = {{0.9, 0.6, 0.5, 0.2}};
      return fixed[app];
    }
  const std::array<std::array<double, 4>, 4> profiles = {{
    {{0.9, 0.6, 0.5, 0.2}}, {{0.4, 0.9, 0.6, 0.2}},
    {{0.6, 0.5, 0.9, 0.2}}, {{0.9, 0.6, 0.5, 0.2}}
  }};
  const std::array<double, 4> boundaries = {{30.0, 60.0, 80.0, duration}};
  double start = 0.0;
  double weighted = 0.0;
  for (uint32_t phase = 0; phase < profiles.size (); ++phase)
    {
      double end = std::min (duration, boundaries[phase]);
      if (end > start)
        {
          weighted += (end - start) * profiles[phase][app];
        }
      start = end;
      if (start >= duration)
        {
          break;
        }
    }
  return duration > 0.0 ? weighted / duration : 0.0;
}

static double
TargetMeanUtility (uint32_t app, double duration)
{
  return MeanUtility (app, "E3", duration);
}

static double
HistogramPercentile (Histogram histogram, uint32_t samples, double percentile)
{
  if (samples == 0 || histogram.GetNBins () == 0)
    {
      return 0.0;
    }
  uint64_t target = static_cast<uint64_t> (std::ceil (samples * percentile));
  uint64_t cumulative = 0;
  for (uint32_t bin = 0; bin < histogram.GetNBins (); ++bin)
    {
      cumulative += histogram.GetBinCount (bin);
      if (cumulative >= target)
        {
          return histogram.GetBinEnd (bin) * 1000.0;
        }
    }
  return histogram.GetBinEnd (histogram.GetNBins () - 1) * 1000.0;
}

static void
TraceQueueSize (Time stopAt)
{
  g_queueFile << Simulator::Now ().GetSeconds () << "," << g_queueDisc->GetQueueSize () << "\n";
  if (Simulator::Now () + MilliSeconds (10) <= stopAt)
    {
      Simulator::Schedule (MilliSeconds (10), &TraceQueueSize, stopAt);
    }
}

static void
TraceSojourn (std::string queueName, Time sojourn)
{
  g_sojournFile << Simulator::Now ().GetSeconds () << "," << queueName << ","
                << sojourn.GetMilliSeconds () << "\n";
}

static void
TraceCwnd (std::string name, uint32_t oldCwnd, uint32_t newCwnd)
{
  g_cwndFile << Simulator::Now ().GetSeconds () << "," << name << ","
             << oldCwnd << "," << newCwnd << "\n";
}

static void
ApplyUtilities (std::array<double, 4> utilities, const std::string& activity)
{
  std::cout << Simulator::Now ().GetSeconds () << "s activity=" << activity << " utility:" << std::endl;
  for (uint32_t i = 0; i < g_sources.size (); ++i)
    {
      NS_ABORT_MSG_IF (!g_sources[i], "Industrial AR OnOff application pointer is null");
      Ptr<Socket> appSocket = g_sources[i]->GetSocket ();
      NS_ABORT_MSG_IF (!appSocket, "Industrial AR source socket has not been created");
      Ptr<TcpSocketBase> socket = DynamicCast<TcpSocketBase> (appSocket);
      NS_ABORT_MSG_IF (!socket, "Industrial AR source socket is not a TcpSocketBase");
      socket->SetCongestionControlUtility (utilities[i]);
      if (!g_cwndTracesConnected)
        {
          socket->TraceConnectWithoutContext ("CongestionWindow",
                                              MakeBoundCallback (&TraceCwnd, g_names[i]));
        }
      std::cout << "  " << g_names[i] << "=" << utilities[i] << std::endl;
    }
  g_cwndTracesConnected = true;
  std::cout << std::endl;
}

int
main (int argc, char *argv[])
{
  double duration = 100.0;
  std::string bottleneckRate = "10Mbps";
  std::string bottleneckDelay = "10ms";
  std::string output = "industrial-ar";
  std::string experiment = "E3";
  bool pcap = true;
  CommandLine cmd;
  cmd.AddValue ("duration", "Simulation duration in seconds", duration);
  cmd.AddValue ("bottleneckRate", "Client-router bottleneck rate", bottleneckRate);
  cmd.AddValue ("bottleneckDelay", "Client-router bottleneck delay", bottleneckDelay);
  cmd.AddValue ("output", "Output prefix for pcap and FlowMonitor files", output);
  cmd.AddValue ("experiment", "Experiment mode: E1 equal, E2 fixed, or E3 dynamic", experiment);
  cmd.AddValue ("pcap", "Write pcap traces", pcap);
  cmd.Parse (argc, argv);
  NS_ABORT_MSG_IF (experiment != "E1" && experiment != "E2" && experiment != "E3",
                   "experiment must be E1, E2, or E3");
  g_experiment = experiment;
  g_cwndFile.open (output + ".cwnd.csv");
  g_cwndFile << "time_s,application,old_cwnd_bytes,new_cwnd_bytes\n";
  g_queueFile.open (output + ".queue.csv");
  g_queueFile << "time_s,queue_bytes\n";
  g_sojournFile.open (output + ".sojourn.csv");
  g_sojournFile << "time_s,queue,sojourn_ms\n";

  Ptr<Node> client = CreateObject<Node> ();
  Ptr<Node> router = CreateObject<Node> ();
  NodeContainer servers;
  servers.Create (4);
  Config::SetDefault ("ns3::TcpL4Protocol::SocketType", TypeIdValue (TcpDctcp::GetTypeId ()));
  Config::SetDefault ("ns3::TcpSocketBase::EcnMode", StringValue ("ClassicEcn"));
  Config::SetDefault ("ns3::TcpDctcp::Utility", DoubleValue (1.0));
  Config::SetDefault ("ns3::TcpSocket::SegmentSize", UintegerValue (1448));
  Config::SetDefault ("ns3::TcpSocket::DelAckCount", UintegerValue (1));
  Config::SetDefault ("ns3::DualQCoupledPi2QueueDisc::QueueLimit", UintegerValue (100000));
  Config::SetDefault ("ns3::DualQCoupledPi2QueueDisc::L4SMarkThresold", TimeValue (MilliSeconds (1)));

  InternetStackHelper internet;
  internet.Install (client);
  internet.Install (router);
  internet.Install (servers);

  PointToPointHelper access;
  access.SetDeviceAttribute ("DataRate", StringValue (bottleneckRate));
  access.SetChannelAttribute ("Delay", StringValue (bottleneckDelay));
  NetDeviceContainer bottleneck = access.Install (client, router);

  TrafficControlHelper dual;
  uint16_t handle = dual.SetRootQueueDisc ("ns3::DualQCoupledPi2QueueDisc");
  dual.AddInternalQueues (handle, 2, "ns3::DropTailQueue", "MaxSize", StringValue ("100000B"));
  QueueDiscContainer qdiscs = dual.Install (bottleneck.Get (0));
  g_queueDisc = DynamicCast<DualQCoupledPi2QueueDisc> (qdiscs.Get (0));
  NS_ABORT_MSG_IF (!g_queueDisc, "Failed to create the DualPI2 queue disc");
  g_queueDisc->TraceConnectWithoutContext ("ClassicSojournTime",
                                           MakeBoundCallback (&TraceSojourn, std::string ("classic")));
  g_queueDisc->TraceConnectWithoutContext ("L4sSojournTime",
                                           MakeBoundCallback (&TraceSojourn, std::string ("l4s")));

  CsmaHelper lan;
  lan.SetChannelAttribute ("DataRate", StringValue ("1Gbps"));
  lan.SetChannelAttribute ("Delay", TimeValue (MicroSeconds (10)));
  NodeContainer lanNodes;
  lanNodes.Add (router);
  lanNodes.Add (servers);
  NetDeviceContainer lanDevices = lan.Install (lanNodes);

  Ipv4AddressHelper address;
  address.SetBase ("10.1.1.0", "255.255.255.0");
  Ipv4InterfaceContainer clientIf = address.Assign (bottleneck);
  address.SetBase ("10.1.2.0", "255.255.255.0");
  Ipv4InterfaceContainer lanIf = address.Assign (lanDevices);
  Ipv4GlobalRoutingHelper::PopulateRoutingTables ();

  const uint16_t basePort = 50000;
  const uint32_t packetSize = 1000;
  for (uint32_t i = 0; i < 4; ++i)
    {
      uint16_t port = basePort + i;
      PacketSinkHelper sink ("ns3::TcpSocketFactory",
                             InetSocketAddress (Ipv4Address::GetAny (), port));
      ApplicationContainer sinkApp = sink.Install (servers.Get (i));
      sinkApp.Start (Seconds (0));
      sinkApp.Stop (Seconds (duration));

      OnOffHelper source ("ns3::TcpSocketFactory",
                          InetSocketAddress (lanIf.GetAddress (i + 1), port));
      source.SetAttribute ("PacketSize", UintegerValue (i == 2 ? 256 : packetSize));
      source.SetAttribute ("DataRate", DataRateValue (DataRate (i == 1 ? "8Mbps" :
                                                          i == 2 ? "40.96kbps" :
                                                          i == 3 ? "3Mbps" : "8Mbps")));
      source.SetAttribute ("OnTime", StringValue (i == 1 ? "ns3::ConstantRandomVariable[Constant=0.5]" :
                                                  "ns3::ConstantRandomVariable[Constant=1]"));
      source.SetAttribute ("OffTime", StringValue (i == 1 ? "ns3::ConstantRandomVariable[Constant=0.5]" :
                                                   "ns3::ConstantRandomVariable[Constant=0]"));
      ApplicationContainer sourceApp = source.Install (client);
      g_sources[i] = DynamicCast<OnOffApplication> (sourceApp.Get (0));
      sourceApp.Start (Seconds (0.1));
      sourceApp.Stop (Seconds (duration - 1));
      NS_LOG_UNCOND (g_names[i] << " flow: client " << clientIf.GetAddress (0)
                              << " -> server " << lanIf.GetAddress (i + 1)
                              << ":" << port << " via TcpDctcp (ECT(1) capable)");
    }

  // E1 keeps reference DCTCP behaviour (utility 1 maps p' = p). E2 freezes
  // paper-style priorities. E3 follows the dynamic activity schedule.
  if (experiment == "E1")
    {
      Simulator::Schedule (Seconds (0.11), &ApplyUtilities,
                           std::array<double, 4>{{1.0, 1.0, 1.0, 1.0}}, "equal-utility");
    }
  else
    {
      Simulator::Schedule (Seconds (0.11), &ApplyUtilities,
                           std::array<double, 4>{{0.9, 0.6, 0.5, 0.2}}, "remote-assistance");
      if (experiment == "E3")
        {
          Simulator::Schedule (Seconds (30), &ApplyUtilities,
                               std::array<double, 4>{{0.4, 0.9, 0.6, 0.2}}, "component-inspection");
          Simulator::Schedule (Seconds (60), &ApplyUtilities,
                               std::array<double, 4>{{0.6, 0.5, 0.9, 0.2}}, "overheating-detection");
          Simulator::Schedule (Seconds (80), &ApplyUtilities,
                               std::array<double, 4>{{0.9, 0.6, 0.5, 0.2}}, "remote-assistance");
        }
    }

  FlowMonitorHelper flowHelper;
  Ptr<FlowMonitor> flowMonitor = flowHelper.InstallAll ();
  Simulator::ScheduleNow (&TraceQueueSize, Seconds (duration));
  if (pcap)
    {
      access.EnablePcap (output + "-bottleneck", bottleneck, true);
    }

  Simulator::Stop (Seconds (duration));
  Simulator::Run ();
  g_cwndFile.close ();
  g_queueFile.close ();
  g_sojournFile.close ();
  flowMonitor->CheckForLostPackets ();
  flowMonitor->SerializeToXmlFile (output + ".flowmon", true, true);
  QueueDisc::Stats queueStats = qdiscs.Get (0)->GetStats ();
  std::ofstream metrics (output + ".applications.csv");
  metrics << "experiment,application,offered_mbps,throughput_mbps,mean_delay_ms,p95_delay_ms,p99_delay_ms,jitter_ms,tx_packets,rx_packets,lost_packets,loss_ratio,mean_control_utility,mean_target_utility,utility_satisfaction\n";
  Ptr<Ipv4FlowClassifier> classifier = DynamicCast<Ipv4FlowClassifier> (flowHelper.GetClassifier ());
  NS_ABORT_MSG_IF (!classifier, "Expected IPv4 FlowMonitor classifier");
  struct ApplicationMetrics
  {
    double throughput;
    double utility;
    double satisfaction;
    ApplicationMetrics () : throughput (0.0), utility (0.0), satisfaction (0.0) {}
  } appMetrics[4];
  const FlowMonitor::FlowStatsContainer& flowStats = flowMonitor->GetFlowStats ();
  double activeSeconds = std::max (1.0, duration - 1.1);
  for (FlowMonitor::FlowStatsContainer::const_iterator it = flowStats.begin ();
       it != flowStats.end (); ++it)
    {
      Ipv4FlowClassifier::FiveTuple tuple = classifier->FindFlow (it->first);
      if (tuple.destinationPort < basePort || tuple.destinationPort >= basePort + 4)
        {
          continue;
        }
      uint32_t app = tuple.destinationPort - basePort;
      const FlowMonitor::FlowStats& stats = it->second;
      appMetrics[app].throughput = stats.rxBytes * 8.0 / activeSeconds / 1e6;
      appMetrics[app].utility = MeanUtility (app, experiment, duration);
      double targetUtility = TargetMeanUtility (app, duration);
      double meanDelay = stats.rxPackets ? stats.delaySum.GetMilliSeconds () / stats.rxPackets : 0.0;
      double jitter = stats.rxPackets > 1 ? stats.jitterSum.GetMilliSeconds () / (stats.rxPackets - 1) : 0.0;
      double lost = std::min<uint32_t> (stats.lostPackets, stats.txPackets);
      double lossRatio = stats.txPackets ? lost / stats.txPackets : 0.0;
      appMetrics[app].satisfaction = std::min (1.0, appMetrics[app].throughput / g_offeredMbps[app]);
      metrics << experiment << "," << g_names[app] << "," << g_offeredMbps[app] << ","
              << appMetrics[app].throughput << "," << meanDelay << ","
              << HistogramPercentile (stats.delayHistogram, stats.rxPackets, 0.95) << ","
              << HistogramPercentile (stats.delayHistogram, stats.rxPackets, 0.99) << ","
              << jitter << "," << stats.txPackets << "," << stats.rxPackets << ","
              << lost << "," << lossRatio << "," << appMetrics[app].utility << "," << targetUtility << ","
              << appMetrics[app].satisfaction << "\n";
    }
  metrics.close ();

  double utilityWeight = 0.0;
  double weightedSatisfaction = 0.0;
  for (uint32_t i = 0; i < 4; ++i)
    {
      if (appMetrics[i].utility == 0.0)
        {
          appMetrics[i].utility = MeanUtility (i, experiment, duration);
          appMetrics[i].satisfaction = std::min (1.0, appMetrics[i].throughput / g_offeredMbps[i]);
        }
      double targetUtility = TargetMeanUtility (i, duration);
      utilityWeight += targetUtility;
      weightedSatisfaction += targetUtility * appMetrics[i].satisfaction;
    }
  std::ofstream networkMetrics (output + ".network.csv");
  networkMetrics << "experiment,mark_ratio,marked_packets,enqueued_packets,drop_ratio,dropped_packets,weighted_utility_satisfaction\n";
  networkMetrics << experiment << ","
                 << (queueStats.nTotalEnqueuedPackets ? static_cast<double> (queueStats.nTotalMarkedPackets) / queueStats.nTotalEnqueuedPackets : 0.0)
                 << "," << queueStats.nTotalMarkedPackets << "," << queueStats.nTotalEnqueuedPackets << ","
                 << (queueStats.nTotalEnqueuedPackets ? static_cast<double> (queueStats.nTotalDroppedPackets) / queueStats.nTotalEnqueuedPackets : 0.0)
                 << "," << queueStats.nTotalDroppedPackets << ","
                 << (utilityWeight ? weightedSatisfaction / utilityWeight : 0.0) << "\n";
  networkMetrics.close ();
  std::cout << "\nDualPI2 queue statistics\n" << queueStats << std::endl;
  Simulator::Destroy ();
  return 0;
}
