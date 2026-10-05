package com.stagepulse.jarvis;

public final class AgencyAgent {
    public final String id;
    public final String name;
    public final String mission;
    public final String capabilities;
    public final String workflow;

    public AgencyAgent(String id, String name, String mission, String capabilities, String workflow) {
        this.id = id;
        this.name = name;
        this.mission = mission;
        this.capabilities = capabilities;
        this.workflow = workflow;
    }

    public String activationPrompt(String task) {
        return "STAGEPULSE AGENT: " + name + "\n"
                + "MISSION: " + mission + "\n"
                + "CAPABILITIES: " + capabilities + "\n"
                + "WORKFLOW: " + workflow + "\n"
                + "TASK: " + task + "\n"
                + "RULE: Teknik varsayım yapma; eksik veri varsa belirt, ölçülebilir ve uygulanabilir çıktı üret.";
    }
}
