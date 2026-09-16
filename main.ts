// To run this code you need to install the following dependencies:
// npm install @google/genai mime
// npm install -D @types/node

import {
  GoogleGenAI,
} from '@google/genai';
import mime from 'mime';
import { writeFile } from 'fs/promises';
import { execFileSync } from 'node:child_process';

async function main() {
  process.loadEnvFile();
  const ai = new GoogleGenAI({
    apiKey: process.env['GEMINI_API_KEY'],
  });
  const config = {
    temperature: 1,
    responseModalities: [
        'audio',
    ],
    speechConfig: {
      voiceConfig: {
        prebuiltVoiceConfig: {
          voiceName: 'Achird',
        }
      }
    },
  };
  const model = 'gemini-3.1-flash-tts-preview';
  const contents = [
    {
      role: 'user',
      parts: [
        {
          text: `Read the following transcript based on the audio profile and director's note.

# Audio Profile
A story teller

# Director's note
Style: Empathetic. Pace: Natural. Accent: Neutral.

## Scene:
A quiet, professional remote workspace.

## Sample Context:
Steady, efficient, and unhurried. Tone is empathetic, crisp, and reassuring.

## Transcript:
Agar tum apni life ko improve karna chahte ho, toh tumne shayad bahut saari productivity techniques try ki hongi. To-do lists, time management apps, morning routines, motivational videos aur countless productivity hacks. Lekin ek important question hai. Kya sirf apne tasks ko efficiently complete karna hi success hai? Ya phir success ka matlab kuch aur bhi hai?

Stephen R. Covey ki famous book, The 7 Habits of Highly Effective People, isi question ko deeply explore karti hai. Ye book sirf productivity ke baare mein nahi hai. Ye actually ek complete framework hai, jo batata hai ki hum apni thinking, habits, relationships aur priorities ko kaise improve kar sakte hain.

Covey ka maanna hai ki long-term success ke liye humein sirf apne behavior ko change karne ki koshish nahi karni chahiye. Humein apni thinking ke foundation ko change karna chahiye. Kyunki agar thinking same rahegi, toh habits ka change bhi zyada der tak nahi chalega.

Book ka journey seven habits ke through hota hai. Aur interesting baat ye hai ki ye seven habits randomly arranged nahi hain. Pehle teen habits tumhe apne aap ko manage karna sikhati hain. Agli teen habits tumhe doosre logon ke saath effectively interact karna sikhati hain. Aur seventh habit tumhe continuously grow aur improve karne ke baare mein batati hai.

Pehli habit hai, Be Proactive.

Proactive hone ka simple matlab hai ki tum apni life ki responsibility khud accept karo. Humari life mein bahut saari cheezein hoti hain jo hum control nahi kar sakte. Weather, economy, doosre logon ka behavior, traffic, unexpected problems aur kabhi-kabhi circumstances bhi.

Lekin ek cheez jo hum control kar sakte hain, woh hai humara response.

Maan lo tumhara exam kharab ho gaya. Ek person keh sakta hai, paper hi bahut difficult tha, teacher ne unfair questions diye, meri preparation ke liye time hi nahi mila. Doosra person same situation ko dekhkar pooch sakta hai, ab main kya improve kar sakta hoon?

Situation same hai, lekin response different hai.

Covey ke according, reactive person apni energy un cheezon par spend karta hai jinhe woh control nahi kar sakta. Proactive person apni energy un cheezon par focus karta hai jin par woh actually action le sakta hai.

Is idea ko samajhne ke liye ek simple distinction hai. Concern aur influence.

Tum duniya mein bahut saari cheezon ko lekar concerned ho sakte ho, lekin tum sab kuch control nahi kar sakte. Isliye apni energy apne Circle of Influence par focus karo. Jo cheezein tumhare control mein hain, un par action lo.

Tum apni preparation control kar sakte ho. Apni discipline control kar sakte ho. Apni communication improve kar sakte ho. Lekin har doosre person ka opinion control nahi kar sakte.

Jab tum ye difference samajh lete ho, tumhari energy complaints se action ki taraf move hone lagti hai.

Ab aate hain second habit par. Begin With the End in Mind.

Iska simple meaning hai, kisi journey par nikalne se pehle ye decide karo ki tum jaana kahan chahte ho.

Imagine karo tum ek building bana rahe ho. Agar architect ke paas blueprint hi nahi hai, toh workers bricks lagana start toh kar sakte hain, lekin final building kya hogi, ye clear nahi hoga.

Life bhi kuch similar hai.

Hum daily busy rehte hain. Classes, assignments, job, meetings, social media, entertainment aur countless small tasks. Lekin kabhi-kabhi hum itne busy ho jaate hain ki ye bhool jaate hain ki hum actually kis direction mein ja rahe hain.

Covey kehta hai ki apni life ke important roles aur values ke baare mein consciously socho.

Tum student ho sakte ho. Developer ho sakte ho. Friend ho sakte ho. Family member ho sakte ho. Future mein entrepreneur ya professional banna chahte ho.

Question ye hai ki in roles mein tum kis type ka person banna chahte ho?

Agar tumhe pata hai ki tum kis direction mein jaana chahte ho, toh daily decisions lena easier ho jaata hai.

Third habit hai, Put First Things First.

Ye habit basically priorities ke baare mein hai.

Hum sabke paas twenty-four hours hain. Problem ye nahi hai ki kisi ke paas zyada time hai aur kisi ke paas kam. Problem ye hai ki hum us time ko kis cheez par spend karte hain.

Imagine karo tumhare paas ek jar hai. Tumhe usmein bade stones, small stones aur sand fill karni hai. Agar tum pehle sand bhar doge, toh bade stones ke liye space nahi bachega.

Lekin agar tum pehle bade stones rakhoge, phir small stones aur finally sand, toh sab kuch fit ho sakta hai.

Life mein bhi big rocks woh cheezein hain jo genuinely important hain. Health, studies, family, relationships, meaningful work, long-term goals.

Small tasks aur random distractions sand ki tarah hain.

Agar tum apna poora din notifications, scrolling aur unnecessary tasks mein spend kar doge, toh important goals ke liye time nahi bachega.

Isliye busy hone ke bajay effective hone ki koshish karo.

Ab pehli teen habits ka result kya hai?

Tum dependent mindset se independent mindset ki taraf move karte ho.

Tum situation ke according react karne ke bajay consciously choose karna seekhte ho. Tum apni destination define karte ho aur phir apni priorities ke according action lete ho.

Lekin life sirf individual success ka naam nahi hai. Hum relationships mein bhi exist karte hain.

Aur isi point par Covey ki next three habits start hoti hain.

Habit number four hai, Think Win-Win.

Iska matlab hai aise solutions dhoondhna jahan dono sides ko value mile.

Hum aksar life ko competition ki tarah dekhte hain. Agar main jeeta, toh doosra haara. Agar doosre person ko benefit mila, toh shayad mujhe loss hua.

Win-Win thinking is mindset ko change karti hai.

Maan lo do students ek project par kaam kar rahe hain. Ek student coding mein strong hai aur doosra presentation aur design mein. Instead of competing over who is more important, dono apni strengths combine kar sakte hain.

Result? Dono better perform karte hain.

Win-Win ka matlab ye nahi hai ki har situation mein compromise karna hi hai. Iska matlab hai mutual benefit ke possibilities dhoondhna.

Aur agar genuine Win-Win possible nahi hai, toh kabhi-kabhi agreement na karna bhi better hota hai rather than forcing a bad deal.

Habit number five hai, Seek First to Understand, Then to Be Understood.

Ye shayad relationships ke liye sabse powerful habits mein se ek hai.

Normally jab koi person humse apni problem share karta hai, hum turant solution dene lagte hain.

Kisi friend ne kaha, mera exam kharab ho gaya.

Hum turant bol dete hain, tension mat le, next time better kar lena.

Technically hum help kar rahe hote hain, lekin humne pehle ye understand hi nahi kiya ki woh person actually feel kya kar raha hai.

Covey ka principle hai, pehle genuinely listen karo.

Understand karne ke liye suno, reply prepare karne ke liye nahi.

Jab kisi person ko feel hota hai ki usse genuinely suna ja raha hai, trust naturally build hota hai.

Aur jab tum doosre person ko properly understand kar lete ho, tab apni perspective explain karna bhi much easier ho jaata hai.

Good communication ka matlab sirf achha bolna nahi hai.

Sometimes, good communication ka matlab achha sunna hota hai.

Habit number six hai, Synergize.

Synergy ka simple idea hai ki different people ki strengths combine karke aisa result create kiya ja sakta hai jo individual efforts se better ho.

Socho ek team mein ek person technical hai, doosra creative hai, teesra communication mein strong hai aur chautha organization mein.

Agar sab log sirf apna-apna kaam karein, toh team functional ho sakti hai.

Lekin agar woh ek doosre ki differences ko advantage ki tarah use karein, toh completely new possibilities create ho sakti hain.

Synergy ka matlab hai differences ko problem nahi, resource samajhna.

Tumhe har person ki tarah sochne ki zarurat nahi hai.

Kabhi-kabhi doosre person ka different perspective hi tumhari biggest learning ban sakta hai.

Aur ab aati hai seventh habit.

Sharpen the Saw.

Imagine karo ek woodcutter ek tree ko continuously cut kar raha hai. Uske paas ek saw hai, lekin saw gradually dull hoti ja rahi hai.

Koi usse kehta hai, saw ko sharpen kar lo.

Woodcutter reply karta hai, mere paas saw sharpen karne ka time nahi hai. Main tree cut karne mein busy hoon.

Funny lagta hai, lekin humari life mein exactly yehi hota hai.

Hum kehte hain, exercise karne ka time nahi hai. Reading karne ka time nahi hai. Rest karne ka time nahi hai. New skill seekhne ka time nahi hai.

Lekin agar hum apne body aur mind ko continuously use karte rahenge bina recovery aur improvement ke, toh eventually performance decline hogi.

Sharpen the Saw ka matlab hai regularly apne aap ko renew karna.

Physically, exercise aur proper rest.

Mentally, reading, learning aur reflection.

Emotionally aur socially, meaningful relationships.

Aur internally, apni values aur purpose ke saath connection.

Ye habit basically remind karti hai ki self-improvement ek one-time project nahi hai.

It's a continuous process.

Ab agar hum poori book ko ek journey ki tarah dekhein, toh seven habits ek beautiful progression create karti hain.

Pehle tum seekhte ho apni life ki responsibility lena.

Phir tum decide karte ho ki tum jaana kahan chahte ho.

Uske baad tum apni priorities ko organize karte ho.

Phir tum doosron ke saath mutually beneficial relationships banana seekhte ho.

Tum genuinely sunna seekhte ho.

Tum differences ke through better results create karna seekhte ho.

Aur finally, tum khud ko continuously renew karte rehte ho.

Is book ka sabse important lesson shayad ye hai ki effectiveness sirf zyada kaam karne ka naam nahi hai.

Kabhi-kabhi humein faster run karne ke bajay ye check karna chahiye ki hum correct direction mein run bhi kar rahe hain ya nahi.

Agar tum bahut productive ho, lekin tumhari priorities galat hain, toh tum simply galat direction mein efficiently travel kar rahe ho.

Isliye apne aap se kuch questions regularly poochho.

Kya main apni life ki responsibility le raha hoon?

Kya mujhe pata hai ki main future mein kya banna chahta hoon?

Kya main important cheezon ko priority de raha hoon?

Kya meri relationships Win-Win thinking par based hain?

Kya main doosron ko genuinely sunta hoon?

Kya main doosron ke different perspectives ko appreciate karta hoon?

Aur sabse important, kya main khud ko continuously improve kar raha hoon?

The 7 Habits of Highly Effective People humein koi magic formula nahi deti.

Instead, ye ek mindset deti hai.

Aisi mindset jahan tum circumstances ke victim banne ke bajay responsibility accept karte ho. Jahan tum short-term distractions ke bajay long-term values ko importance dete ho. Jahan success sirf personal achievement nahi, balki strong relationships aur continuous growth bhi hai.

Aur shayad effectiveness ka real meaning bhi yahi hai.

Sirf zyada kaam karna nahi.

Sirf successful dikhna nahi.

Balki ek aisi life build karna jahan tumhari actions tumhari values ke saath aligned hon.

Toh agli baar jab tum apni productivity improve karne ke liye koi naya hack search karo, ek minute ke liye rukna.

Khud se poochna, kya mujhe ek aur productivity hack chahiye?

Ya mujhe apni habits aur thinking ke foundation ko change karne ki zarurat hai?

Because real change usually starts from the inside.

Agar tumhe ye book summary useful lagi, toh video ko like karo, channel ko subscribe karo, aur comments mein batao, in seven habits mein se kaunsi habit tum apni life mein sabse pehle develop karna chahoge?

Milte hain next book ke saath.

Keep reading. Keep learning. Keep building.`,
        },
      ],
    },
  ];

  const response = await ai.models.generateContentStream({
    model,
    config,
    contents,
  });

  const pcmChunks: Buffer[] = [];
  let mimeType = '';
  for await (const chunk of response) {
    if (!chunk.candidates || !chunk.candidates[0].content || !chunk.candidates[0].content.parts) {
      continue;
    }
    const inlineData = chunk.candidates[0].content.parts[0].inlineData;
    if (inlineData) {
      mimeType = inlineData.mimeType || mimeType;
      pcmChunks.push(Buffer.from(inlineData.data || '', 'base64'));
    } else {
      console.log(chunk.text);
    }
  }

  if (pcmChunks.length === 0) {
    console.error('No audio data received.');
    return;
  }

  const pcmData = Buffer.concat(pcmChunks);
  const wavBuffer = mime.getExtension(mimeType)
    ? pcmData
    : Buffer.concat([createWavHeader(pcmData.length, parseMimeType(mimeType)), pcmData]);

  const wavPath = 'output.wav';
  await writeFile(wavPath, wavBuffer);
  console.log(`Saved ${wavPath}`);

  const mp3Path = 'output.mp3';
  try {
    execFileSync('ffmpeg', ['-y', '-i', wavPath, '-codec:a', 'libmp3lame', '-qscale:a', '2', mp3Path]);
    console.log(`Saved ${mp3Path}`);
  } catch (err) {
    console.error('ffmpeg conversion to mp3 failed:', err);
  }
}

main();

interface WavConversionOptions {
  numChannels : number,
  sampleRate: number,
  bitsPerSample: number
}

function parseMimeType(mimeType : string) {
  const [fileType, ...params] = mimeType.split(';').map(s => s.trim());
  const [_, format] = fileType.split('/');

  const options : WavConversionOptions = {
    numChannels: 1,
    sampleRate: 24000,
    bitsPerSample: 16,
  };

  if (format && format.startsWith('L')) {
    const bits = parseInt(format.slice(1), 10);
    if (!isNaN(bits)) {
      options.bitsPerSample = bits;
    }
  }

  for (const param of params) {
    const [key, value] = param.split('=').map(s => s.trim());
    if (key === 'rate') {
      const rate = parseInt(value, 10);
      if (!isNaN(rate)) {
        options.sampleRate = rate;
      }
    }
  }

  return options as WavConversionOptions;
}

function createWavHeader(dataLength: number, options: WavConversionOptions) {
  const {
    numChannels,
    sampleRate,
    bitsPerSample,
  } = options;

  // http://soundfile.sapp.org/doc/WaveFormat

  const byteRate = sampleRate * numChannels * bitsPerSample / 8;
  const blockAlign = numChannels * bitsPerSample / 8;
  const buffer = Buffer.alloc(44);

  buffer.write('RIFF', 0);                      // ChunkID
  buffer.writeUInt32LE(36 + dataLength, 4);     // ChunkSize
  buffer.write('WAVE', 8);                      // Format
  buffer.write('fmt ', 12);                     // Subchunk1ID
  buffer.writeUInt32LE(16, 16);                 // Subchunk1Size (PCM)
  buffer.writeUInt16LE(1, 20);                  // AudioFormat (1 = PCM)
  buffer.writeUInt16LE(numChannels, 22);        // NumChannels
  buffer.writeUInt32LE(sampleRate, 24);         // SampleRate
  buffer.writeUInt32LE(byteRate, 28);           // ByteRate
  buffer.writeUInt16LE(blockAlign, 32);         // BlockAlign
  buffer.writeUInt16LE(bitsPerSample, 34);      // BitsPerSample
  buffer.write('data', 36);                     // Subchunk2ID
  buffer.writeUInt32LE(dataLength, 40);         // Subchunk2Size

  return buffer;
}


