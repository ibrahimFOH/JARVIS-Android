package com.stagepulse.jarvis;

import android.content.Context;
import android.graphics.*;
import android.view.View;

public final class HudView extends View {
    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
    private float phase = 0f;
    private boolean active = false;
    private final int gold = Color.rgb(212,175,55);
    private final int gold2 = Color.rgb(143,116,32);
    private final int white = Color.rgb(242,242,242);

    public HudView(Context c) { super(c); setLayerType(View.LAYER_TYPE_SOFTWARE, null); }

    public void setActive(boolean value) { active=value; invalidate(); }

    @Override protected void onDraw(Canvas c) {
        super.onDraw(c);
        float w=getWidth(), h=getHeight(), cx=w/2f, cy=h/2f;
        float base=Math.min(w,h)*0.22f;
        p.setStyle(Paint.Style.STROKE);
        p.setStrokeCap(Paint.Cap.ROUND);
        c.drawColor(Color.rgb(5,5,5));
        p.setColor(Color.rgb(16,18,20)); p.setStrokeWidth(1);
        c.drawLine(22,cy,w-22,cy,p); c.drawLine(cx,22,cx,h-22,p);

        float pulse=(float)(Math.sin(phase)*0.08+1.0);
        float glow=base*1.02f*pulse;
        p.setShadowLayer(active ? 18 : 8,0,0,active ? gold : gold2);
        for(int i=0;i<5;i++){
            float r=base*(0.62f+i*0.16f)+(active?(float)Math.sin(phase+i)*2f:0f);
            p.setColor(i<3 ? gold2 : Color.rgb(80,66,25));
            p.setStrokeWidth(i==2?2.5f:1.2f);
            c.drawCircle(cx,cy,r,p);
        }
        p.setColor(gold); p.setStrokeWidth(2);
        RectF arc=new RectF(cx-glow,cy-glow,cx+glow,cy+glow);
        c.drawArc(arc,phase*57f, active?110f:70f,false,p);
        c.drawArc(arc,phase*57f+180f, active?75f:45f,false,p);
        p.setStyle(Paint.Style.FILL); p.setShadowLayer(active?22:10,0,0,gold);
        c.drawCircle(cx,cy,base*0.13f,p);
        p.clearShadowLayer(); p.setColor(white); p.setTextAlign(Paint.Align.CENTER); p.setTextSize(Math.max(14,base*0.10f));
        c.drawText(active?"LISTENING":"JARVIS",cx,cy+base*0.46f,p);
        phase += active?0.11f:0.035f;
        postInvalidateDelayed(33);
    }
}
